"""
Research module Flask blueprint.

Mounted at /api/research/* by backend/research/__init__.py:register_blueprint
when RESEARCH_ENABLED=true. All endpoints return JSON.

Endpoint summary:
    GET  /health                        — module liveness check
    GET  /availability                  — pre-flight CLI / runner detection
    POST /start                         — begin a research task
    GET  /status/<task_id>              — poll progress
    GET  /result/<task_id>              — fetch compiled document + citations
    POST /promote/<task_id>             — write compiled doc to project, return project_id
    POST /cancel/<task_id>              — request cancellation
"""

from __future__ import annotations

import logging
import threading
import traceback
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from . import config as research_config
from .models import (
    ResearchPhase,
    ResearchTask,
    load_task,
    save_task,
)
from .orchestrator import ResearchOrchestrator, list_registered_runners, get_runner

logger = logging.getLogger('research.api')

research_bp = Blueprint('research', __name__)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


@research_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'service': 'research',
        'enabled_runners': research_config.RUNNERS,
        'default_runner': research_config.DEFAULT_RUNNER,
        'registered_runners': list_registered_runners(),
    })


# ---------------------------------------------------------------------------
# /availability
# ---------------------------------------------------------------------------


@research_bp.route('/availability', methods=['GET'])
def availability():
    """Probe each enabled runner and report whether it can be used right now.

    The frontend uses this on Step 0 page load to populate the runner picker
    with green / yellow / grey indicators per runner. No CLI subprocesses
    actually run a sub-topic during this call — only the cheap is_available()
    check on each runner.
    """
    results: List[Dict[str, Any]] = []
    for runner_name in research_config.RUNNERS:
        try:
            runner = get_runner(runner_name)
            avail = runner.is_available()
            results.append(avail.to_dict())
        except KeyError:
            results.append({
                'name': runner_name,
                'available': False,
                'auth_ok': False,
                'reason': f"Runner {runner_name!r} is enabled in RESEARCH_RUNNERS but no implementation is registered",
                'version': None,
            })
        except Exception as e:
            logger.warning(f"Availability probe for {runner_name} crashed: {e}")
            results.append({
                'name': runner_name,
                'available': False,
                'auth_ok': False,
                'reason': f"{type(e).__name__}: {e}",
                'version': None,
            })

    return jsonify({
        'runners': results,
        'default_runner': research_config.DEFAULT_RUNNER,
        'enabled_runners': research_config.RUNNERS,
    })


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


@research_bp.route('/start', methods=['POST'])
def start():
    """Begin a research task. Returns immediately with task_id; the frontend
    polls /status/<task_id> for progress."""
    body = request.get_json(silent=True) or {}
    prompt = (body.get('prompt') or '').strip()
    simulation_requirement = (body.get('simulation_requirement') or '').strip()
    runner_choice = (body.get('runner_choice') or research_config.DEFAULT_RUNNER).strip()
    project_name = (body.get('project_name') or '').strip() or None
    additional_context = (body.get('additional_context') or '').strip() or None

    if not prompt:
        return jsonify({'success': False, 'error': 'prompt is required'}), 400
    if not simulation_requirement:
        return jsonify({'success': False, 'error': 'simulation_requirement is required'}), 400

    # Validate the runner choice early
    if runner_choice not in research_config.RUNNERS:
        return jsonify({
            'success': False,
            'error': f"runner_choice {runner_choice!r} not in RESEARCH_RUNNERS={research_config.RUNNERS}",
        }), 400

    # Lazy imports for the same reasons as in the orchestrator
    try:
        from app.models.project import ProjectManager
        from app.models.task import TaskManager
    except Exception as e:
        return jsonify({'success': False, 'error': f"failed to import app dependencies: {e}"}), 500

    # Create the project + task
    try:
        project = ProjectManager.create_project(name=project_name or f"Research: {prompt[:60]}")
        project.simulation_requirement = simulation_requirement
        ProjectManager.save_project(project)
    except Exception as e:
        logger.exception("Failed to create research project")
        return jsonify({'success': False, 'error': f"project creation failed: {e}"}), 500

    tm = TaskManager()
    task_id = tm.create_task(
        task_type='research',
        metadata={
            'project_id': project.project_id,
            'runner_choice': runner_choice,
        },
    )

    research_task = ResearchTask.new(
        task_id=task_id,
        project_id=project.project_id,
        prompt=prompt,
        simulation_requirement=simulation_requirement,
        runner_choice=runner_choice,
        additional_context=additional_context,
    )
    save_task(research_task)

    # Spawn the daemon thread
    def _worker():
        try:
            orchestrator = ResearchOrchestrator(research_task)
            orchestrator.run()
        except Exception:
            logger.exception(f"Research worker for task {task_id} crashed at top level")

    t = threading.Thread(target=_worker, name=f"research-{task_id[:8]}", daemon=True)
    t.start()

    return jsonify({
        'success': True,
        'task_id': task_id,
        'project_id': project.project_id,
        'runner': runner_choice,
    })


# ---------------------------------------------------------------------------
# /status/<task_id>
# ---------------------------------------------------------------------------


@research_bp.route('/status/<task_id>', methods=['GET'])
def status(task_id: str):
    task = load_task(task_id)
    if task is None:
        return jsonify({'success': False, 'error': f"task {task_id} not found"}), 404
    # Return the slim version (no compiled_text) — frontend uses /result for the doc
    return jsonify({
        'success': True,
        'task': task.to_dict(),
    })


# ---------------------------------------------------------------------------
# /result/<task_id>
# ---------------------------------------------------------------------------


@research_bp.route('/result/<task_id>', methods=['GET'])
def result(task_id: str):
    task = load_task(task_id)
    if task is None:
        return jsonify({'success': False, 'error': f"task {task_id} not found"}), 404
    if task.phase != ResearchPhase.COMPLETED:
        return jsonify({
            'success': False,
            'error': f"task is in phase {task.phase.value}, not completed",
        }), 409
    return jsonify({
        'success': True,
        'task_id': task.task_id,
        'project_id': task.project_id,
        'compiled_text': task.compiled_text,
        'citations': task.citations,
        'sub_topics': [s.to_dict() for s in task.sub_topics],
    })


# ---------------------------------------------------------------------------
# /promote/<task_id>
# ---------------------------------------------------------------------------


@research_bp.route('/promote/<task_id>', methods=['POST'])
def promote(task_id: str):
    """Write the compiled document to the project's extracted_text.txt and
    advance the project so the existing Step 1 ontology generator can pick it up.

    The frontend calls this when the user has reviewed the preview and wants
    to continue. Returns the project_id so the frontend can navigate to Step 1.
    """
    task = load_task(task_id)
    if task is None:
        return jsonify({'success': False, 'error': f"task {task_id} not found"}), 404
    if task.phase != ResearchPhase.COMPLETED:
        return jsonify({
            'success': False,
            'error': f"cannot promote task in phase {task.phase.value}",
        }), 409
    if not task.compiled_text:
        return jsonify({'success': False, 'error': 'task has no compiled_text'}), 409

    try:
        from app.models.project import ProjectManager
    except Exception as e:
        return jsonify({'success': False, 'error': f"app.models.project not importable: {e}"}), 500

    project = ProjectManager.get_project(task.project_id)
    if project is None:
        return jsonify({'success': False, 'error': f"project {task.project_id} not found"}), 404

    try:
        ProjectManager.save_extracted_text(task.project_id, task.compiled_text)
        # Record source metadata on the project so the existing ontology
        # generator and downstream consumers know it came from research.
        project.total_text_length = len(task.compiled_text)
        project.files = [{
            'original_filename': f'research_{task_id[:8]}.md',
            'saved_filename': f'research_{task_id[:8]}.md',
            'path': f'<research:{task_id}>',
            'size': len(task.compiled_text.encode('utf-8')),
        }]
        ProjectManager.save_project(project)
    except Exception as e:
        logger.exception("Failed to promote research task")
        return jsonify({'success': False, 'error': f"promote failed: {e}"}), 500

    return jsonify({
        'success': True,
        'project_id': task.project_id,
    })


# ---------------------------------------------------------------------------
# /cancel/<task_id>
# ---------------------------------------------------------------------------


@research_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel(task_id: str):
    try:
        from app.models.task import TaskManager
    except Exception as e:
        return jsonify({'success': False, 'error': f"task manager unavailable: {e}"}), 500
    tm = TaskManager()
    ok = tm.request_cancel(task_id)
    return jsonify({'success': ok})
