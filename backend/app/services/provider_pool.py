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
class ProviderModel:
    """A single model offered by a provider, with optional quota metadata."""
    id: str
    daily_token_budget: Optional[int] = None
    rpd: Optional[int] = None


@dataclass
class ProviderEntry:
    """An entry in the multi-provider pool.

    A provider has EITHER a single `model` (legacy / single-model env config)
    OR a list of `models` (multi-model, from the catalogue or LLM_<NAME>_MODELS).
    Exactly one of the two is populated. `is_multi_model()` distinguishes.
    """
    name: str
    api_key: str
    base_url: str
    model: Optional[str] = None
    models: Optional[List[ProviderModel]] = None
    daily_token_budget: Optional[int] = None
    source: str = 'env_single'  # one of: catalogue / env_list / env_single

    def __post_init__(self):
        # Coerce dict → ProviderModel when constructed from Config.get_provider_pool()
        if self.models and isinstance(self.models[0], dict):
            self.models = [ProviderModel(**m) for m in self.models]

    def is_multi_model(self) -> bool:
        return bool(self.models and len(self.models) >= 1)

    def model_ids(self) -> List[str]:
        if self.is_multi_model():
            return [m.id for m in self.models]
        return [self.model] if self.model else []

    def probe_model_id(self) -> Optional[str]:
        """Which model to use for the reachability probe. First if multi, else the single."""
        if self.is_multi_model():
            return self.models[0].id
        return self.model

    def to_public_dict(self) -> Dict[str, Any]:
        """Same as asdict but redacts the API key."""
        d = {
            'name': self.name,
            'base_url': self.base_url,
            'daily_token_budget': self.daily_token_budget,
            'api_key_set': bool(self.api_key),
            'source': self.source,
        }
        if self.is_multi_model():
            d['models'] = [asdict(m) for m in self.models]
        else:
            d['model'] = self.model
        return d


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
        """Send a minimal chat completion request to verify the provider is reachable.

        Multi-model providers are probed against their first model (whichever
        one the catalogue or LLM_<NAME>_MODELS listed first). A single health
        record per provider is sufficient because they share the same API key
        and base URL — if the endpoint is up, all models are reachable.
        """
        start = time.time()
        health = ProviderHealth(name=entry.name, reachable=False)
        probe_model = entry.probe_model_id()
        if not probe_model:
            health.error = "No model available to probe"
            return health
        try:
            client = OpenAI(
                api_key=entry.api_key,
                base_url=entry.base_url,
                timeout=timeout,
            )
            response = client.chat.completions.create(
                model=probe_model,
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
    ) -> Dict[Any, Dict[str, str]]:
        """Randomly assign each agent to (provider, model).

        Two-level allocation:
          1. Outer: agents → providers, weighted random with replacement.
             User-supplied `weights` dict biases this level. Uniform if None.
          2. Inner (multi-model providers only): the agents that landed on a
             multi-model provider are sub-allocated across that provider's
             models using weighted random sampling proportional to each
             model's daily_token_budget. Missing/zero quotas fall back to
             uniform within the provider.

        Args:
            agent_ids: list of agent identifiers
            seed: random seed for reproducibility (None = system random)
            only_reachable: probe the pool first and skip unreachable providers
            weights: {provider_name: float} — outer-level distribution weights

        Returns:
            dict mapping agent_id -> {"provider": str, "model": str}

        Backwards-compat note: older call sites expected {agent_id: str}.
        The shape changed in v1.1.3 to carry the resolved model alongside
        the provider. agent_model_assignment.build_assignment was updated
        in the same commit.
        """
        candidates = self.entries
        if only_reachable:
            healths = self.probe_all()
            reachable = {h.name for h in healths if h.reachable}
            candidates = [e for e in self.entries if e.name in reachable]

        if not candidates:
            raise ValueError("No providers available for allocation")

        rng = random.Random(seed)

        # ---- Outer allocation: agents → providers ----
        weight_vec = None
        if weights:
            weight_vec = [max(0.0, float(weights.get(e.name, 0.0))) for e in candidates]
            if sum(weight_vec) <= 0:
                weight_vec = None

        if weight_vec is None:
            outer_picks = [rng.choice(candidates) for _ in agent_ids]
        else:
            outer_picks = rng.choices(candidates, weights=weight_vec, k=len(agent_ids))

        # ---- Inner allocation: agents-on-multi-model-providers → models ----
        # Group agent indices by provider so we can batch-sample within each
        # group using quota-proportional weights.
        by_provider: Dict[str, List[int]] = {}
        for i, entry in enumerate(outer_picks):
            by_provider.setdefault(entry.name, []).append(i)

        assignments: Dict[Any, Dict[str, str]] = {}
        for provider_name, indices in by_provider.items():
            entry = next(e for e in candidates if e.name == provider_name)
            if entry.is_multi_model():
                model_ids = [m.id for m in entry.models]
                model_weights = [
                    (m.daily_token_budget if m.daily_token_budget and m.daily_token_budget > 0 else 0)
                    for m in entry.models
                ]
                if sum(model_weights) <= 0:
                    # No quota info — uniform within the provider's models
                    model_weights = None
                if model_weights is None:
                    inner_picks = [rng.choice(model_ids) for _ in indices]
                else:
                    inner_picks = rng.choices(model_ids, weights=model_weights, k=len(indices))
            else:
                # Single-model provider: every agent on this provider gets the same model
                inner_picks = [entry.model] * len(indices)

            for idx, model_id in zip(indices, inner_picks):
                agent_id = agent_ids[idx]
                assignments[agent_id] = {
                    'provider': provider_name,
                    'model': model_id,
                }
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
