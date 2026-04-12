"""Runner implementations for the research module.

Each runner is responsible for taking a SubTopic and producing a
ResearchSummary. The runners are interchangeable — the orchestrator picks
which one to use based on user choice and availability probe.
"""

from .base import (
    CLIRunner,
    AvailabilityResult,
    ResearchRunnerError,
    ResearchTimeoutError,
    ResearchAuthError,
)

__all__ = [
    'CLIRunner',
    'AvailabilityResult',
    'ResearchRunnerError',
    'ResearchTimeoutError',
    'ResearchAuthError',
]
