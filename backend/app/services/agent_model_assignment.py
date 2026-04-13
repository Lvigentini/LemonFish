"""
Agent-to-Model Assignment Service (Phase 6)

Bridges the Phase 4 ProviderPool to the Phase 6 multi-model persona
simulation by:

  1. Allocating each agent to a provider from the pool (seeded random)
  2. Writing the full per-agent model config to a JSON file that the
     OASIS subprocess can read at startup

The OASIS subprocess then monkey-patches
`oasis.social_agent.agents_generator.generate_*_agent_graph` to
create a distinct per-agent model backend instead of sharing one.

Format of agent_model_assignments.json:
    {
      "seed": 42,
      "created_at": "2026-04-12T...",
      "pool": ["gemini", "openrouter"],
      "assignments": {
        "0": {
          "provider": "gemini",
          "api_key": "AIza...",
          "base_url": "https://...",
          "model": "gemini-3-flash-preview"
        },
        ...
      }
    }
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Config
from .provider_pool import ProviderPool

logger = logging.getLogger(__name__)

ASSIGNMENT_FILENAME = 'agent_model_assignments.json'


def build_assignment(
    simulation_dir: Path,
    agent_ids: List[Any],
    seed: Optional[int] = None,
    only_reachable: bool = False,
    weights: Optional[Dict[str, float]] = None,
) -> Optional[Path]:
    """Allocate agents across the multi-provider pool and persist to disk.

    Returns the path to the written JSON file, or None if the pool is not
    configured (in which case the simulation uses the single LLM_SIMULATION_*
    / LLM_* config as before).

    `weights` optionally biases the distribution; see ProviderPool.allocate_agents.
    """
    pool = ProviderPool()
    if not pool:
        return None

    assignments = pool.allocate_agents(
        agent_ids=agent_ids,
        seed=seed,
        only_reachable=only_reachable,
        weights=weights,
    )

    # Resolve each agent's provider entry to full config.
    # Since v1.1.3 allocate_agents returns {agent_id: {"provider": str, "model": str}}
    # with the per-agent model already chosen (quota-proportional for multi-model
    # providers). We pull api_key + base_url from the pool entry.
    detailed: Dict[str, Dict[str, Any]] = {}
    for agent_id, choice in assignments.items():
        provider_name = choice['provider']
        entry = pool.get(provider_name)
        if entry is None:
            continue
        detailed[str(agent_id)] = {
            'provider': provider_name,
            'api_key': entry.api_key,
            'base_url': entry.base_url,
            'model': choice['model'],
        }

    doc = {
        'seed': seed,
        'created_at': datetime.utcnow().isoformat(),
        'pool': pool.names(),
        'only_reachable': only_reachable,
        'weights': weights or None,
        'agent_count': len(detailed),
        'assignments': detailed,
    }

    simulation_dir = Path(simulation_dir)
    simulation_dir.mkdir(parents=True, exist_ok=True)
    output_path = simulation_dir / ASSIGNMENT_FILENAME
    tmp = output_path.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    tmp.replace(output_path)

    logger.info(
        f"Wrote agent-to-model assignment: {len(detailed)} agents across "
        f"{len(pool)} providers to {output_path}"
    )
    return output_path


def load_assignment(simulation_dir: Path) -> Optional[Dict[str, Any]]:
    """Load an assignment file if present."""
    path = Path(simulation_dir) / ASSIGNMENT_FILENAME
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load agent model assignment: {e}")
        return None


def get_distribution_summary(assignment_doc: Dict[str, Any]) -> Dict[str, int]:
    """Return a {provider: agent_count} summary for logging/reporting."""
    from collections import Counter
    provider_counts = Counter()
    for entry in assignment_doc.get('assignments', {}).values():
        provider_counts[entry.get('provider', 'unknown')] += 1
    return dict(provider_counts)
