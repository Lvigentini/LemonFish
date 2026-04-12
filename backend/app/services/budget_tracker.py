"""
Budget Tracker (Phase 7.10)

Aggregates today's token consumption across all simulations and
compares it to the daily budgets configured per provider.

Complements Phase 3 (per-simulation tracking) and Phase 4 (per-provider
budget config) by providing a pool-wide "how much have we used today"
view that's independent of any specific simulation.

Storage: reads from backend/uploads/token_usage/*.json (Phase 3 format).
Budgets: read from Config.get_provider_pool() (Phase 4).
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

from ..config import Config

logger = logging.getLogger(__name__)

_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / 'uploads' / 'token_usage'


def _parse_ts(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.min


def _load_all_usage_files(since: datetime) -> List[Dict[str, Any]]:
    """Load all token_usage/*.json files updated since the given datetime."""
    if not _STORAGE_DIR.exists():
        return []
    results = []
    for p in _STORAGE_DIR.glob('*.json'):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                doc = json.load(f)
            last_updated = _parse_ts(doc.get('last_updated', doc.get('created_at', '')))
            if last_updated >= since:
                results.append(doc)
        except Exception as e:
            logger.debug(f"Could not read {p.name}: {e}")
    return results


def get_daily_totals() -> Dict[str, Any]:
    """Return today's token consumption aggregated across all simulations,
    broken down by provider/model, with budget remaining.
    """
    # "Today" = rolling last 24h (simpler than calendar-day-aware logic)
    since = datetime.utcnow() - timedelta(hours=24)

    # Load configured provider pool for budgets
    pool = Config.get_provider_pool()
    pool_by_endpoint = {}  # key: base_url+model -> (provider_name, budget)
    for entry in pool:
        key = f"{entry['base_url']}||{entry['model']}"
        pool_by_endpoint[key] = (entry['name'], entry.get('daily_token_budget'))

    # Aggregate consumption across all simulations in the last 24h
    consumed_by_endpoint = defaultdict(lambda: {
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0,
        'calls': 0,
        'simulations': set(),
    })

    for doc in _load_all_usage_files(since):
        sim_id = doc.get('simulation_id', 'unknown')
        for step_name, step_data in doc.get('steps', {}).items():
            for model_key, model_data in step_data.get('models_used', {}).items():
                # model_key is "model @ base_url" — try to match endpoints
                consumed_by_endpoint[model_key]['input_tokens'] += model_data.get('input_tokens', 0)
                consumed_by_endpoint[model_key]['output_tokens'] += model_data.get('output_tokens', 0)
                consumed_by_endpoint[model_key]['total_tokens'] += (
                    model_data.get('input_tokens', 0) + model_data.get('output_tokens', 0)
                )
                consumed_by_endpoint[model_key]['calls'] += model_data.get('calls', 0)
                consumed_by_endpoint[model_key]['simulations'].add(sim_id)

    # Build response rows
    rows = []
    for model_key, usage in consumed_by_endpoint.items():
        # Try to match against pool budgets
        provider_name = None
        budget = None
        # model_key format: "model @ base_url"
        if ' @ ' in model_key:
            model_part, base_url_part = model_key.split(' @ ', 1)
            lookup = f"{base_url_part}||{model_part}"
            if lookup in pool_by_endpoint:
                provider_name, budget = pool_by_endpoint[lookup]
        rows.append({
            'endpoint': model_key,
            'provider': provider_name,
            'total_tokens': usage['total_tokens'],
            'input_tokens': usage['input_tokens'],
            'output_tokens': usage['output_tokens'],
            'calls': usage['calls'],
            'simulation_count': len(usage['simulations']),
            'daily_budget': budget,
            'remaining': (budget - usage['total_tokens']) if budget else None,
            'percent_used': round(100 * usage['total_tokens'] / budget, 1) if budget else None,
            'over_budget': (budget is not None and usage['total_tokens'] > budget),
        })

    # Add providers in the pool that have zero consumption (for completeness)
    used_endpoints = {row['endpoint'] for row in rows}
    for entry in pool:
        key = f"{entry['model']} @ {entry['base_url']}"
        if key not in used_endpoints:
            rows.append({
                'endpoint': key,
                'provider': entry['name'],
                'total_tokens': 0,
                'input_tokens': 0,
                'output_tokens': 0,
                'calls': 0,
                'simulation_count': 0,
                'daily_budget': entry.get('daily_token_budget'),
                'remaining': entry.get('daily_token_budget'),
                'percent_used': 0.0 if entry.get('daily_token_budget') else None,
                'over_budget': False,
            })

    # Sort by percent_used desc (unbudgeted last)
    rows.sort(key=lambda r: (r['percent_used'] is None, -(r['percent_used'] or 0)))

    grand_total = sum(r['total_tokens'] for r in rows)

    return {
        'since_utc': since.isoformat(),
        'grand_total_tokens': grand_total,
        'per_endpoint': rows,
        'warnings': [
            f"{r['provider'] or r['endpoint']} is at {r['percent_used']}% of daily budget"
            for r in rows if r['percent_used'] is not None and r['percent_used'] >= 80
        ],
    }
