"""
Research orchestrator — Plan → Research → Synthesise.

Lifecycle of a /api/research/start invocation:

    1. Endpoint creates a project (ProjectManager.create_project)
    2. Endpoint creates a ResearchTask in TaskManager and on disk
    3. Endpoint spawns a daemon thread running ResearchOrchestrator.run()
    4. The orchestrator drives the three phases, persisting state on every
       transition so the frontend's status polling sees real progress
    5. On success it writes the compiled document to the project's
       extracted_text.txt and marks the project ONTOLOGY_GENERATED-ready
    6. On failure it marks the task FAILED, leaves the project in CREATED
       state, and lets the frontend offer a retry

The orchestrator does not import the runners eagerly — they are looked up
by name through a small registry so the API fallback runner does not pull
in the CLI subprocess code paths until they are actually used.
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from . import config as research_config
from .models import (
    ResearchPhase,
    ResearchSummary,
    ResearchTask,
    SubTopic,
    SubTopicStatus,
    save_task,
)
from .runners.base import (
    AvailabilityResult,
    CLIRunner,
    ResearchAuthError,
    ResearchRunnerError,
    ResearchTimeoutError,
)

logger = logging.getLogger('research.orchestrator')


# ---------------------------------------------------------------------------
# Runner registry
# ---------------------------------------------------------------------------

# Mapping from runner name to a zero-arg factory. Lazy imports so the API
# runner does not pull in CLI runner modules and vice versa.
_RUNNER_FACTORIES: Dict[str, Callable[[], CLIRunner]] = {}


def _register_runner(name: str, factory: Callable[[], CLIRunner]) -> None:
    _RUNNER_FACTORIES[name] = factory


def _make_api_runner() -> CLIRunner:
    from .runners.api_runner import ApiRunner
    return ApiRunner()


_register_runner('api', _make_api_runner)

# CLI runners are registered when their modules exist. Wrap each in a
# try/except so a missing or broken runner module does not break the others.
try:
    from .runners.claude_runner import ClaudeRunner  # type: ignore
    _register_runner('claude', lambda: ClaudeRunner())
except Exception:
    pass
try:
    from .runners.codex_runner import CodexRunner  # type: ignore
    _register_runner('codex', lambda: CodexRunner())
except Exception:
    pass
try:
    from .runners.kimi_runner import KimiRunner  # type: ignore
    _register_runner('kimi', lambda: KimiRunner())
except Exception:
    pass


def get_runner(name: str) -> CLIRunner:
    """Look up a runner by name. Raises KeyError if not registered."""
    factory = _RUNNER_FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"Unknown runner: {name!r}. Known: {sorted(_RUNNER_FACTORIES)}")
    return factory()


def list_registered_runners() -> List[str]:
    return sorted(_RUNNER_FACTORIES.keys())


# ---------------------------------------------------------------------------
# Plan / Synthesise prompts
# ---------------------------------------------------------------------------

PLAN_SYSTEM_PROMPT = (
    "You are a research planner for LemonFish, a multi-agent prediction simulation engine. "
    "Your job is to take a vague intent (a prompt) and decompose it into 3-8 concrete "
    "research sub-topics that, taken together, would give a researcher enough material to "
    "later run an agent-based social simulation about the topic. "
    "Each sub-topic must be concrete enough to be answered by a single web-search-and-summarise "
    "session. Avoid duplication. Avoid overly broad framings. Each sub-topic should have "
    "2-4 specific research questions."
)


def _plan_user_prompt(prompt: str, simulation_requirement: str, additional_context: Optional[str], min_n: int, max_n: int) -> str:
    extra = f"\n\nAdditional context:\n{additional_context}" if additional_context else ""
    return (
        f"User prompt: {prompt}\n\n"
        f"Simulation requirement: {simulation_requirement}{extra}\n\n"
        f"Produce {min_n}-{max_n} sub-topics. Respond with ONLY a JSON object of this shape:\n"
        '{\n'
        '  "sub_topics": [\n'
        '    {"topic": "...", "questions": ["...", "..."]},\n'
        '    ...\n'
        '  ]\n'
        '}\n'
        f"No prose outside the JSON. Do not number the topics."
    )


SYNTHESIS_SYSTEM_PROMPT = (
    "You are a research synthesiser for LemonFish. You will be given several sub-topic "
    "summaries that were each researched independently. Your job is to merge them into "
    "ONE coherent compiled document that reads like a curated background brief. The "
    "downstream pipeline will treat your output as if it were an uploaded source document "
    "for a knowledge graph build, so it must be: factual, concrete, neutral in tone, and "
    "rich in named entities (organisations, people, places, products, regulations, dates, "
    "numbers). Preserve citations from the inputs as inline references where they appear."
)


def _synthesis_user_prompt(
    task: ResearchTask,
    summaries: List[ResearchSummary],
    min_chars: int,
    max_chars: int,
) -> str:
    parts = []
    for s in summaries:
        st = task.sub_topics[s.sub_topic_index] if 0 <= s.sub_topic_index < len(task.sub_topics) else None
        topic_label = st.topic if st else f"Sub-topic {s.sub_topic_index}"
        parts.append(
            f"=== SUB-TOPIC {s.sub_topic_index + 1}: {topic_label} ===\n"
            f"(researched by: {s.runner})\n\n"
            f"{s.body}\n"
        )
    summaries_block = '\n'.join(parts)
    return (
        f"Original user prompt: {task.prompt}\n"
        f"Simulation requirement: {task.simulation_requirement}\n\n"
        f"Below are independent research summaries from {len(summaries)} sub-topics. "
        f"Merge them into a single compiled background brief, organised by topic. "
        f"Target length: {min_chars}-{max_chars} characters. Use clear section headings. "
        f"Preserve specific facts (dates, numbers, named entities). Eliminate redundancy "
        f"between sub-topics. Do NOT add information that is not supported by the summaries.\n\n"
        f"{summaries_block}\n\n"
        f"Now write the compiled document."
    )


# ---------------------------------------------------------------------------
# Cancellation support
# ---------------------------------------------------------------------------


class _CancelChecker:
    """Thin wrapper around TaskManager.is_cancelled so the orchestrator can
    poll cooperatively without importing TaskManager at module load time."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._task_manager = None

    def _get(self):
        if self._task_manager is None:
            from app.models.task import TaskManager
            self._task_manager = TaskManager()
        return self._task_manager

    def is_cancelled(self) -> bool:
        try:
            return self._get().is_cancelled(self.task_id)
        except Exception:
            return False


class CancelledError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# The orchestrator
# ---------------------------------------------------------------------------


class ResearchOrchestrator:
    """Drives one ResearchTask through Plan → Research → Synthesise.

    Designed to run in a background daemon thread. Construct with the task
    + a runner, then call .run(). All state is mirrored to disk on every
    phase transition.
    """

    def __init__(self, task: ResearchTask):
        self.task = task
        self.cancel = _CancelChecker(task.task_id)

    # -- public entry point --------------------------------------------------

    def run(self) -> None:
        try:
            self._set_phase(ResearchPhase.PLANNING, message="Decomposing prompt into sub-topics")
            self._check_cancel()
            self._do_plan()

            self._set_phase(ResearchPhase.RESEARCHING, message=f"Researching {len(self.task.sub_topics)} sub-topics in parallel")
            self._check_cancel()
            self._do_research()

            self._set_phase(ResearchPhase.SYNTHESISING, message="Compiling results")
            self._check_cancel()
            self._do_synthesis()

            self._set_phase(ResearchPhase.COMPLETED, message="Research complete")
            self._update_task_manager(status='completed', progress=100, message='Research complete')
            logger.info(f"Research task {self.task.task_id} completed: {len(self.task.compiled_text)} chars compiled")

        except CancelledError:
            self.task.phase = ResearchPhase.CANCELLED
            self.task.error = "Cancelled by user"
            save_task(self.task)
            self._update_task_manager(status='cancelled', message='Cancelled by user')
            logger.info(f"Research task {self.task.task_id} cancelled")
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Research task {self.task.task_id} failed: {e}\n{tb}")
            self.task.phase = ResearchPhase.FAILED
            self.task.error = f"{type(e).__name__}: {e}"
            save_task(self.task)
            self._update_task_manager(status='failed', message=str(e), error=str(e))

    # -- phase 1: plan -------------------------------------------------------

    def _do_plan(self) -> None:
        from app.config import Config
        from app.utils.llm_client import LLMClient

        cfg = Config.get_step_llm_config('research_plan')
        client = LLMClient(**cfg)

        user_prompt = _plan_user_prompt(
            prompt=self.task.prompt,
            simulation_requirement=self.task.simulation_requirement,
            additional_context=self.task.additional_context,
            min_n=research_config.PLAN_MIN_SUBTOPICS,
            max_n=research_config.PLAN_MAX_SUBTOPICS,
        )

        try:
            data = client.chat_json(
                messages=[
                    {'role': 'system', 'content': PLAN_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.4,
                max_tokens=2000,
            )
        except Exception as e:
            raise RuntimeError(f"Plan phase LLM call failed: {e}") from e

        raw_topics = data.get('sub_topics') if isinstance(data, dict) else None
        if not isinstance(raw_topics, list) or not raw_topics:
            raise RuntimeError(
                f"Plan phase produced no sub_topics. Raw response: {str(data)[:300]}"
            )

        # Clamp to configured min/max — favour the LLM's count when in range.
        max_n = research_config.PLAN_MAX_SUBTOPICS
        min_n = research_config.PLAN_MIN_SUBTOPICS
        clamped = raw_topics[:max_n]
        if len(clamped) < min_n:
            logger.warning(
                f"Plan phase produced {len(clamped)} sub-topics, below min {min_n}. Proceeding anyway."
            )

        sub_topics: List[SubTopic] = []
        for i, raw in enumerate(clamped):
            if not isinstance(raw, dict):
                continue
            topic = str(raw.get('topic') or '').strip()
            if not topic:
                continue
            questions = raw.get('questions') or []
            if not isinstance(questions, list):
                questions = []
            sub_topics.append(SubTopic(
                index=i,
                topic=topic,
                questions=[str(q).strip() for q in questions if str(q).strip()],
            ))

        if not sub_topics:
            raise RuntimeError("Plan phase produced no valid sub-topics after parsing")

        self.task.sub_topics = sub_topics
        save_task(self.task)
        self._update_task_manager(progress=15, message=f"Planned {len(sub_topics)} sub-topics")

    # -- phase 2: research ---------------------------------------------------

    def _do_research(self) -> None:
        runner_name = self.task.runner_choice or research_config.DEFAULT_RUNNER
        try:
            runner = get_runner(runner_name)
        except KeyError as e:
            raise RuntimeError(str(e)) from e

        # Check the runner is actually usable before fanning out
        avail = runner.is_available()
        if not avail.available:
            raise RuntimeError(
                f"Runner {runner_name!r} is not available: {avail.reason or 'unknown'}"
            )
        if not avail.auth_ok:
            raise RuntimeError(
                f"Runner {runner_name!r} is installed but not authenticated: {avail.reason or 'check credentials'}"
            )

        system_prompt = (
            "You are a research agent for LemonFish, a multi-agent prediction simulation "
            "engine. You will be given a single sub-topic with research questions and a set "
            "of source materials. Produce a focused, factual summary that: cites sources "
            "inline (use [1], [2], ... corresponding to SOURCE 1, SOURCE 2 in the input), "
            "preserves named entities, dates, and numbers, and explicitly notes when a "
            "question is not answered by the available sources. Aim for 600-1200 words. "
            "Output format: prose only, no markdown headings beyond a single H2 for the topic."
        )

        # Run sub-topics in parallel. Each one is independent.
        max_workers = max(1, min(research_config.MAX_PARALLEL, len(self.task.sub_topics)))
        timeout = research_config.AGENT_TIMEOUT
        completed_count = 0
        total = len(self.task.sub_topics)

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='research-agent') as pool:
            future_to_index: Dict[Any, int] = {}
            for st in self.task.sub_topics:
                if self.cancel.is_cancelled():
                    raise CancelledError()
                st.runner = runner_name
                st.status = SubTopicStatus.RUNNING
                st.started_at = datetime.now().isoformat()
                save_task(self.task)
                future = pool.submit(self._run_one_subtopic, runner, st, system_prompt, timeout)
                future_to_index[future] = st.index

            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                self._check_cancel()
                try:
                    summary = future.result()
                    self.task.summaries.append(summary)
                    self.task.sub_topics[idx].status = SubTopicStatus.COMPLETED
                    self.task.sub_topics[idx].finished_at = datetime.now().isoformat()
                except (ResearchTimeoutError, ResearchAuthError, ResearchRunnerError) as e:
                    logger.warning(f"Sub-topic {idx} failed: {e}")
                    self.task.sub_topics[idx].status = SubTopicStatus.FAILED
                    self.task.sub_topics[idx].finished_at = datetime.now().isoformat()
                    self.task.sub_topics[idx].error = str(e)
                except Exception as e:
                    logger.exception(f"Sub-topic {idx} crashed unexpectedly")
                    self.task.sub_topics[idx].status = SubTopicStatus.FAILED
                    self.task.sub_topics[idx].finished_at = datetime.now().isoformat()
                    self.task.sub_topics[idx].error = f"{type(e).__name__}: {e}"

                completed_count += 1
                # Map research progress into the 15-85% range so plan and synthesis
                # have room at the ends.
                pct = 15 + int(70 * completed_count / total)
                save_task(self.task)
                self._update_task_manager(
                    progress=pct,
                    message=f"Research: {completed_count}/{total} sub-topics complete",
                )

        # Need at least one successful summary to proceed
        successful = [s for s in self.task.summaries]
        if not successful:
            raise RuntimeError(
                "Research phase produced no successful summaries — all sub-topics failed"
            )

    def _run_one_subtopic(
        self,
        runner: CLIRunner,
        sub_topic: SubTopic,
        system_prompt: str,
        timeout: int,
    ) -> ResearchSummary:
        start = time.monotonic()
        summary = runner.run(sub_topic, system_prompt, timeout)
        elapsed = time.monotonic() - start
        logger.info(
            f"Sub-topic {sub_topic.index} ({sub_topic.topic[:40]!r}) completed by {runner.name} "
            f"in {elapsed:.1f}s, {len(summary.body)} chars, {len(summary.citations)} citations"
        )
        return summary

    # -- phase 3: synthesise -------------------------------------------------

    def _do_synthesis(self) -> None:
        from app.config import Config
        from app.utils.llm_client import LLMClient

        cfg = Config.get_step_llm_config('research_synthesis')
        client = LLMClient(**cfg)

        # Sort summaries by sub-topic index for stable ordering
        ordered = sorted(self.task.summaries, key=lambda s: s.sub_topic_index)

        user_prompt = _synthesis_user_prompt(
            task=self.task,
            summaries=ordered,
            min_chars=research_config.SYNTHESIS_MIN_CHARS,
            max_chars=research_config.SYNTHESIS_MAX_CHARS,
        )

        try:
            compiled = client.chat(
                messages=[
                    {'role': 'system', 'content': SYNTHESIS_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.4,
                max_tokens=8000,
            )
        except Exception as e:
            raise RuntimeError(f"Synthesis phase LLM call failed: {e}") from e

        compiled = compiled.strip()
        if not compiled:
            raise RuntimeError("Synthesis phase returned empty content")

        # Aggregate unique citations from all summaries (preserving order)
        seen = set()
        all_citations: List[str] = []
        for s in ordered:
            for url in s.citations:
                if url and url not in seen:
                    seen.add(url)
                    all_citations.append(url)

        # Append a "Sources" section if the model didn't already include URLs.
        # The downstream ontology generator benefits from named source URLs.
        if all_citations and 'http' not in compiled[-2000:]:
            compiled += '\n\n--- SOURCES ---\n'
            for i, url in enumerate(all_citations, start=1):
                compiled += f"[{i}] {url}\n"

        self.task.compiled_text = compiled
        self.task.citations = all_citations
        save_task(self.task)
        self._update_task_manager(progress=95, message="Synthesis complete")

    # -- helpers -------------------------------------------------------------

    def _set_phase(self, phase: ResearchPhase, message: str = '') -> None:
        self.task.phase = phase
        save_task(self.task)
        if message:
            logger.info(f"[{self.task.task_id}] {phase.value}: {message}")

    def _check_cancel(self) -> None:
        if self.cancel.is_cancelled():
            raise CancelledError()

    def _update_task_manager(
        self,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Mirror state into TaskManager so the existing task polling pattern works."""
        try:
            from app.models.task import TaskManager, TaskStatus
            tm = TaskManager()
            kwargs: Dict[str, Any] = {}
            if status is not None:
                kwargs['status'] = TaskStatus(status)
            if progress is not None:
                kwargs['progress'] = progress
            if message is not None:
                kwargs['message'] = message
            if error is not None:
                kwargs['error'] = error
            if kwargs:
                tm.update_task(self.task.task_id, **kwargs)
        except Exception as e:
            logger.warning(f"Failed to mirror state to TaskManager: {e}")
