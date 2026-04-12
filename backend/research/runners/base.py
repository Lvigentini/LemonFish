"""
Runner abstract base class and common types.

A runner is anything that can take a SubTopic + system prompt and return a
ResearchSummary. The orchestrator does not care whether the runner is a
local CLI subprocess (claude / codex / kimi) or an API loop (api). Runners
just need to:

    1. Report whether they are available (via is_available)
    2. Run a single sub-topic to completion (via run)
    3. Raise ResearchRunnerError on failure with a human-readable reason

Runners may be invoked concurrently from a ThreadPoolExecutor. Concrete
implementations must be thread-safe (or document otherwise).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ..models import ResearchSummary, SubTopic


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ResearchRunnerError(RuntimeError):
    """Base class for runner failures. The orchestrator catches this and
    marks the affected sub-topic as failed without aborting the whole task."""


class ResearchTimeoutError(ResearchRunnerError):
    """Raised when a runner exceeds its agent timeout."""


class ResearchAuthError(ResearchRunnerError):
    """Raised when a runner cannot authenticate (bad API key, expired
    OAuth token, missing CLI login, etc)."""


# ---------------------------------------------------------------------------
# Availability probe result
# ---------------------------------------------------------------------------


@dataclass
class AvailabilityResult:
    """Result of probing whether a runner is usable on this host.

    Returned by /api/research/availability so the frontend picker can show
    each runner with a clear status:

        available=True  auth_ok=True   → green: usable
        available=True  auth_ok=False  → yellow: installed but not authed
        available=False                → grey: not installed
    """
    name: str
    available: bool
    auth_ok: bool = False
    reason: Optional[str] = None
    version: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'available': self.available,
            'auth_ok': self.auth_ok,
            'reason': self.reason,
            'version': self.version,
        }


# ---------------------------------------------------------------------------
# Runner ABC
# ---------------------------------------------------------------------------


class CLIRunner(ABC):
    """Abstract base for all research runners.

    The 'CLI' in the name is historical — the API fallback runner inherits
    from this same class so the orchestrator can treat them uniformly.
    """

    name: str = 'unknown'

    @abstractmethod
    def is_available(self) -> AvailabilityResult:
        """Probe whether this runner can be used right now.

        Should be cheap to call (no LLM calls, no long subprocess invocations).
        Frontend hits this on every page load.
        """

    @abstractmethod
    def run(self, sub_topic: SubTopic, system_prompt: str, timeout: int) -> ResearchSummary:
        """Execute one sub-topic and return its summary.

        Args:
            sub_topic: the sub-topic to research (single SubTopic from the Plan phase)
            system_prompt: instructions to the runner about what shape of output to produce
            timeout: max seconds the runner is allowed to take

        Returns:
            A ResearchSummary with body and citations populated.

        Raises:
            ResearchAuthError: if the runner cannot authenticate
            ResearchTimeoutError: if the runner exceeds the timeout
            ResearchRunnerError: any other failure
        """
