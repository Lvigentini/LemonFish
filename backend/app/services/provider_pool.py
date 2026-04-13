"""
Multi-Provider Pool & Probe

Manages a pool of LLM providers and answers two questions:
  1. Which providers are currently reachable?
  2. Given N items (agents, calls), how do we distribute them across the pool?

Foundation for the multi-model persona assignment feature. Per-agent
routing into OASIS is wired via backend/scripts/oasis_model_patch.py.

This module delivers:
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
        weights: Optional[Dict[str, float]] = None,
    ) -> Dict[Any, str]:
        """Randomly assign each agent to a provider.

        Args:
            agent_ids: list of agent identifiers
            seed: random seed for reproducibility (None = system random)
            only_reachable: if True, probe the pool first and skip unreachable providers
            weights: optional {provider_name: float} distribution weights.
                Missing/zero weights = never assigned. None = uniform.

        Returns:
            dict mapping agent_id -> provider name

        Weights exist for quota management only: users bias the distribution
        so providers with larger daily budgets absorb more agents. Assignment
        stays random (with replacement) within the weighted pool.
        """
        candidates = self.entries
        if only_reachable:
            healths = self.probe_all()
            reachable = {h.name for h in healths if h.reachable}
            candidates = [e for e in self.entries if e.name in reachable]

        if not candidates:
            raise ValueError("No providers available for allocation")

        rng = random.Random(seed)

        weight_vec = None
        if weights:
            weight_vec = [max(0.0, float(weights.get(e.name, 0.0))) for e in candidates]
            if sum(weight_vec) <= 0:
                weight_vec = None

        assignments: Dict[Any, str] = {}
        if weight_vec is None:
            for agent_id in agent_ids:
                assignments[agent_id] = rng.choice(candidates).name
        else:
            picks = rng.choices(candidates, weights=weight_vec, k=len(agent_ids))
            for agent_id, chosen in zip(agent_ids, picks):
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
