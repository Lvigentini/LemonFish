"""
Research module data models and persistent storage.

The research orchestrator runs in a background thread and produces three
artefacts in sequence:
    1. A list of SubTopics from the Plan phase
    2. A ResearchSummary per SubTopic from the Research phase (parallel)
    3. A compiled document from the Synthesise phase

Run-time progress and the final compiled document are persisted to
uploads/research/{task_id}/state.json so that:
    - The frontend can poll status across server restarts
    - The /promote endpoint can write extracted_text.txt without holding
      the entire compiled document in memory
    - Failed tasks leave forensic state on disk for debugging

We deliberately do NOT use TaskManager's in-memory store as the source of
truth — that store does not survive a restart. We do, however, mirror the
top-level status into a TaskManager task so the existing frontend task
polling pattern (/api/research/status/<task_id>) works without changes.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Storage layout
# ---------------------------------------------------------------------------

# Lazy import to avoid pulling in app.config (and torch via downstream
# imports) at module load time. The directory is computed once on first
# access and cached.
_research_dir_cache: Optional[str] = None
_research_dir_lock = threading.Lock()


def _get_research_dir() -> str:
    """Return uploads/research/, creating it if needed.

    Resolved relative to the same UPLOAD_FOLDER the rest of the app uses,
    via app.config.Config. Imported lazily so this module can still be
    inspected without the full app environment.
    """
    global _research_dir_cache
    if _research_dir_cache is not None:
        return _research_dir_cache
    with _research_dir_lock:
        if _research_dir_cache is not None:
            return _research_dir_cache
        try:
            from app.config import Config
            base = Config.UPLOAD_FOLDER
        except Exception:
            # Fall back to a sibling of the working directory. Used only by
            # unit tests / isolated imports where Config isn't reachable.
            base = os.path.abspath(os.path.join(os.getcwd(), 'uploads'))
        target = os.path.join(base, 'research')
        os.makedirs(target, exist_ok=True)
        _research_dir_cache = target
        return target


def _get_task_dir(task_id: str) -> str:
    target = os.path.join(_get_research_dir(), task_id)
    os.makedirs(target, exist_ok=True)
    return target


def _get_state_path(task_id: str) -> str:
    return os.path.join(_get_task_dir(task_id), 'state.json')


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class ResearchPhase(str, Enum):
    """Coarse phase tracker for the orchestrator. The frontend uses this
    to render which stage of the pipeline is currently running."""
    PENDING = 'pending'
    PLANNING = 'planning'
    RESEARCHING = 'researching'
    SYNTHESISING = 'synthesising'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class SubTopicStatus(str, Enum):
    """Per-sub-topic agent status. The frontend ResearchProgress component
    renders one row per sub-topic with this state."""
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SKIPPED = 'skipped'


@dataclass
class SubTopic:
    """A single research question produced by the Plan phase and consumed
    by exactly one runner during the Research phase."""
    index: int                       # 0-based index for ordering
    topic: str                       # short title (e.g. "Regulatory landscape")
    questions: List[str]             # specific research questions to answer
    status: SubTopicStatus = SubTopicStatus.QUEUED
    runner: Optional[str] = None     # which runner picked it up (claude / api / ...)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'topic': self.topic,
            'questions': list(self.questions),
            'status': self.status.value,
            'runner': self.runner,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'error': self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubTopic':
        return cls(
            index=int(data['index']),
            topic=data['topic'],
            questions=list(data.get('questions') or []),
            status=SubTopicStatus(data.get('status', 'queued')),
            runner=data.get('runner'),
            started_at=data.get('started_at'),
            finished_at=data.get('finished_at'),
            error=data.get('error'),
        )


@dataclass
class ResearchSummary:
    """Output of a single runner for a single sub-topic. The runners write
    free-form prose into `body` and parse out citation URLs into `citations`.
    The synthesis phase consumes a list of these."""
    sub_topic_index: int
    runner: str
    body: str
    citations: List[str] = field(default_factory=list)
    token_usage: Optional[Dict[str, int]] = None  # input/output if the runner can report it

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchSummary':
        return cls(
            sub_topic_index=int(data['sub_topic_index']),
            runner=data['runner'],
            body=data.get('body', ''),
            citations=list(data.get('citations') or []),
            token_usage=data.get('token_usage'),
        )


@dataclass
class ResearchTask:
    """Top-level state for one /api/research/start invocation.

    Persisted to uploads/research/{task_id}/state.json after every meaningful
    state transition. The frontend polls /api/research/status/<task_id>
    which returns this dataclass serialised to JSON.
    """
    task_id: str
    project_id: str
    prompt: str
    simulation_requirement: str
    runner_choice: str
    additional_context: Optional[str] = None
    created_at: str = ''
    updated_at: str = ''
    phase: ResearchPhase = ResearchPhase.PENDING
    sub_topics: List[SubTopic] = field(default_factory=list)
    summaries: List[ResearchSummary] = field(default_factory=list)
    compiled_text: str = ''
    citations: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @classmethod
    def new(
        cls,
        task_id: str,
        project_id: str,
        prompt: str,
        simulation_requirement: str,
        runner_choice: str,
        additional_context: Optional[str] = None,
    ) -> 'ResearchTask':
        now = datetime.now().isoformat()
        return cls(
            task_id=task_id,
            project_id=project_id,
            prompt=prompt,
            simulation_requirement=simulation_requirement,
            runner_choice=runner_choice,
            additional_context=additional_context,
            created_at=now,
            updated_at=now,
        )

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'project_id': self.project_id,
            'prompt': self.prompt,
            'simulation_requirement': self.simulation_requirement,
            'runner_choice': self.runner_choice,
            'additional_context': self.additional_context,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'phase': self.phase.value,
            'sub_topics': [s.to_dict() for s in self.sub_topics],
            'summaries': [s.to_dict() for s in self.summaries],
            'compiled_text_length': len(self.compiled_text),
            'citations': list(self.citations),
            'error': self.error,
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """Like to_dict but includes the full compiled_text. Used by the
        on-disk state file and the /result endpoint."""
        out = self.to_dict()
        out['compiled_text'] = self.compiled_text
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchTask':
        return cls(
            task_id=data['task_id'],
            project_id=data['project_id'],
            prompt=data['prompt'],
            simulation_requirement=data['simulation_requirement'],
            runner_choice=data['runner_choice'],
            additional_context=data.get('additional_context'),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            phase=ResearchPhase(data.get('phase', 'pending')),
            sub_topics=[SubTopic.from_dict(s) for s in data.get('sub_topics', [])],
            summaries=[ResearchSummary.from_dict(s) for s in data.get('summaries', [])],
            compiled_text=data.get('compiled_text', ''),
            citations=list(data.get('citations') or []),
            error=data.get('error'),
        )


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

_save_lock = threading.Lock()


def save_task(task: ResearchTask) -> None:
    """Atomically write task state to disk. Safe to call from any thread."""
    task.touch()
    state_path = _get_state_path(task.task_id)
    tmp_path = state_path + '.tmp'
    with _save_lock:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(task.to_full_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, state_path)


def load_task(task_id: str) -> Optional[ResearchTask]:
    """Load a task by id. Returns None if no state file exists."""
    state_path = _get_state_path(task_id)
    if not os.path.exists(state_path):
        return None
    with open(state_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return ResearchTask.from_dict(data)


def list_tasks(limit: int = 50) -> List[Dict[str, Any]]:
    """List all known research tasks (most recent first), without loading
    the full compiled_text into memory. Returns each as a summary dict."""
    research_dir = _get_research_dir()
    if not os.path.isdir(research_dir):
        return []
    entries = []
    for task_id in os.listdir(research_dir):
        task = load_task(task_id)
        if task is not None:
            entries.append(task.to_dict())  # to_dict (not to_full_dict) — strips compiled_text
    entries.sort(key=lambda d: d.get('created_at', ''), reverse=True)
    return entries[:limit]
