"""
Research module configuration.

All settings are read from environment variables. The module's master switch
is RESEARCH_ENABLED — when false (the default), the main app does not register
the research blueprint at all.

Per-phase LLM routing (LLM_RESEARCH_PLAN_*, LLM_RESEARCH_SYNTHESIS_*) is
handled by the existing Config.get_step_llm_config() helper from Phase 2 and
does not need its own constants here. The orchestrator simply calls
get_step_llm_config('research_plan') / ('research_synthesis').
"""

import os
from typing import List


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _list_env(name: str, default: List[str]) -> List[str]:
    raw = os.environ.get(name, '').strip()
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(',') if item.strip()]


def is_enabled() -> bool:
    """Master switch — whether to register the research blueprint at all."""
    return _bool_env('RESEARCH_ENABLED', default=False)


# Which runners to enable. Subset of: claude, codex, kimi, api.
# The frontend availability probe will further filter this against actual
# CLI installation status.
RUNNERS: List[str] = _list_env('RESEARCH_RUNNERS', default=['api'])

# Default runner if the frontend does not pick one explicitly.
DEFAULT_RUNNER: str = os.environ.get('RESEARCH_DEFAULT_RUNNER', 'api').strip() or 'api'

# Parallelism — how many sub-topic agents run concurrently.
MAX_PARALLEL: int = int(os.environ.get('RESEARCH_MAX_PARALLEL', '5'))

# Per-agent timeout in seconds. CLI tools doing web search can take a while.
AGENT_TIMEOUT: int = int(os.environ.get('RESEARCH_AGENT_TIMEOUT', '600'))

# Plan-phase guardrails on how many sub-topics the planner can produce.
PLAN_MIN_SUBTOPICS: int = int(os.environ.get('RESEARCH_PLAN_MIN_SUBTOPICS', '3'))
PLAN_MAX_SUBTOPICS: int = int(os.environ.get('RESEARCH_PLAN_MAX_SUBTOPICS', '8'))

# Target compiled-document length range. The synthesis prompt asks the LLM
# to land within this band so the output looks like a typical uploaded doc.
SYNTHESIS_MIN_CHARS: int = int(os.environ.get('RESEARCH_SYNTHESIS_MIN_CHARS', '8000'))
SYNTHESIS_MAX_CHARS: int = int(os.environ.get('RESEARCH_SYNTHESIS_MAX_CHARS', '40000'))

# Per-runner DDG search depth for the API fallback.
API_RUNNER_SEARCH_RESULTS: int = int(os.environ.get('RESEARCH_API_SEARCH_RESULTS', '8'))
API_RUNNER_FETCH_TOP: int = int(os.environ.get('RESEARCH_API_FETCH_TOP', '4'))
