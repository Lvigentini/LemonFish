"""
Multi-Provider Pool & Probe (Phase 4)

Manages a pool of LLM providers and answers two questions:
  1. Which providers are currently reachable?
  2. Given N items (agents, calls), how do we distribute them across the pool?

This is the foundation for Phase 6 (multi-model persona assignment).
The actual per-agent simulation routing still needs OASIS integration
work — see docs/implementation_plan.md Phase 6 and
docs/new_features_planning.md for the full design.

This phase delivers:
  - Provider pool config parsing (from Config.get_provider_pool)
  - Provider reachability probe (ping each provider with a tiny call)
  - Random agent-to-provider allocation (seeded, reproducible)
  - Per-provider token consumption caps (informational for now)
"""

import logging
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError
from ..config import Config
from ..utils.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


@dataclass
class ProviderEntry:
    name: str
    api_key: str
    base_url: str
    model: str
    daily_token_budget: Optional[int] = None

    def to_public_dict(self) -> Dict[str, Any]:
        """Same as asdict but redacts the API key."""
        return {
            'name': self.name,
            'base_url': self.base_url,
            'model': self.model,
            'daily_token_budget': self.daily_token_budget,
            'api_key_set': bool(self.api_key),
        }


@dataclass
class ProviderHealth:
    name: str
    reachable: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    model_responded: bool = False
    sample_input_tokens: int = 0
    sample_output_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProviderPool:
    """Loads provider entries from Config and performs probes/allocation."""

    def __init__(self, entries: Optional[List[ProviderEntry]] = None):
        if entries is not None:
            self.entries = entries
        else:
            raw = Config.get_provider_pool()
            self.entries = [ProviderEntry(**e) for e in raw]

    def __bool__(self) -> bool:
        return len(self.entries) > 0

    def __len__(self) -> int:
        return len(self.entries)

    def names(self) -> List[str]:
        return [e.name for e in self.entries]

    def get(self, name: str) -> Optional[ProviderEntry]:
        for e in self.entries:
            if e.name == name:
                return e
        return None

    def probe_one(self, entry: ProviderEntry, timeout: float = 8.0) -> ProviderHealth:
        """Send a minimal chat completion request to verify the provider is reachable."""
        start = time.time()
        health = ProviderHealth(name=entry.name, reachable=False)
        try:
            client = OpenAI(
                api_key=entry.api_key,
                base_url=entry.base_url,
                timeout=timeout,
            )
            response = client.chat.completions.create(
                model=entry.model,
                messages=[
                    {"role": "system", "content": "Reply with the single word OK."},
                    {"role": "user", "content": "OK"},
                ],
                max_tokens=5,
                temperature=0,
            )
            health.reachable = True
            health.latency_ms = round((time.time() - start) * 1000, 1)
            content = (response.choices[0].message.content or "").strip() if response.choices else ""
            health.model_responded = bool(content)
            usage = getattr(response, 'usage', None)
            if usage is not None:
                health.sample_input_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                health.sample_output_tokens = getattr(usage, 'completion_tokens', 0) or 0
        except APIStatusError as e:
            health.error = f"HTTP {e.status_code}: {e.message[:200] if hasattr(e, 'message') else str(e)[:200]}"
        except (APIConnectionError, APITimeoutError) as e:
            health.error = f"{type(e).__name__}: {str(e)[:200]}"
        except Exception as e:
            health.error = f"{type(e).__name__}: {str(e)[:200]}"
        return health

    def probe_all(self, timeout: float = 8.0) -> List[ProviderHealth]:
        """Probe every provider in the pool. Returns health records in pool order."""
        return [self.probe_one(e, timeout=timeout) for e in self.entries]

    def allocate_agents(
        self,
        agent_ids: List[Any],
        seed: Optional[int] = None,
        only_reachable: bool = False,
    ) -> Dict[Any, str]:
        """Randomly assign each agent to a provider.

        Args:
            agent_ids: list of agent identifiers (will be assigned)
            seed: random seed for reproducibility (None = system random)
            only_reachable: if True, probe the pool first and skip unreachable providers

        Returns:
            dict mapping agent_id -> provider name

        Design note: assignment is uniform random, NOT role-based.
        See docs/new_features_planning.md for the rationale.
        """
        candidates = self.entries
        if only_reachable:
            healths = self.probe_all()
            reachable = {h.name for h in healths if h.reachable}
            candidates = [e for e in self.entries if e.name in reachable]

        if not candidates:
            raise ValueError("No providers available for allocation")

        rng = random.Random(seed)
        assignments: Dict[Any, str] = {}
        for agent_id in agent_ids:
            chosen = rng.choice(candidates)
            assignments[agent_id] = chosen.name
        return assignments

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            'size': len(self.entries),
            'providers': [e.to_public_dict() for e in self.entries],
        }


def get_pool_summary() -> Dict[str, Any]:
    """Convenience: return public summary of the currently configured pool."""
    pool = ProviderPool()
    if not pool:
        return {
            'configured': False,
            'message': 'Multi-provider pool not configured. Set LLM_PROVIDERS to enable.',
            'size': 0,
            'providers': [],
        }
    return {
        'configured': True,
        **pool.to_public_dict(),
    }
