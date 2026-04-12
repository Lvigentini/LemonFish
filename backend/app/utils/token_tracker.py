"""
Token Usage Tracker
Records LLM token consumption per pipeline step. Thread-safe.

Usage pattern:
    from .token_tracker import TokenTracker

    # Set context for current thread (e.g. at the start of a step)
    TokenTracker.set_context(simulation_id='sim_abc', step='ontology')

    # LLMClient automatically records usage via record_usage() on each call

    # At the end, get totals
    totals = TokenTracker.get_totals('sim_abc')
    # {'ontology': {'input': 12000, 'output': 2000, 'calls': 1, 'model': '...'}, ...}

The tracker persists to /app/backend/uploads/token_usage/{simulation_id}.json
so it survives server restarts.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

_thread_local = threading.local()
_file_lock = threading.Lock()

# Storage location (relative to app package)
_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / 'uploads' / 'token_usage'


def _ensure_storage_dir() -> None:
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _storage_path(simulation_id: str) -> Path:
    return _STORAGE_DIR / f'{simulation_id}.json'


def _load(simulation_id: str) -> Dict[str, Any]:
    path = _storage_path(simulation_id)
    if not path.exists():
        return {'simulation_id': simulation_id, 'created_at': datetime.utcnow().isoformat(), 'steps': {}}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read token usage file {path}: {e}")
        return {'simulation_id': simulation_id, 'created_at': datetime.utcnow().isoformat(), 'steps': {}}


def _save(simulation_id: str, data: Dict[str, Any]) -> None:
    _ensure_storage_dir()
    path = _storage_path(simulation_id)
    tmp_path = path.with_suffix('.json.tmp')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


class TokenTracker:
    """Thread-local context + per-simulation file-backed token usage tracking."""

    @staticmethod
    def set_context(simulation_id: Optional[str] = None, step: Optional[str] = None) -> None:
        """Set the tracking context for the current thread.

        Pass simulation_id=None to disable tracking for this thread.
        """
        _thread_local.simulation_id = simulation_id
        _thread_local.step = step

    @staticmethod
    def clear_context() -> None:
        _thread_local.simulation_id = None
        _thread_local.step = None

    @staticmethod
    def get_context() -> tuple:
        """Return (simulation_id, step) for the current thread."""
        return (
            getattr(_thread_local, 'simulation_id', None),
            getattr(_thread_local, 'step', None),
        )

    @staticmethod
    def record_usage(
        input_tokens: int,
        output_tokens: int,
        model: str,
        base_url: Optional[str] = None,
        step_override: Optional[str] = None,
    ) -> None:
        """Record a single LLM call.

        Uses the current thread's simulation_id/step unless step_override is given.
        Silently no-ops if no simulation_id is set (e.g. ad-hoc calls outside a pipeline).
        """
        simulation_id, step = TokenTracker.get_context()
        if step_override:
            step = step_override
        if not simulation_id:
            return
        if not step:
            step = 'unknown'

        with _file_lock:
            data = _load(simulation_id)
            steps = data.setdefault('steps', {})
            step_data = steps.setdefault(step, {
                'calls': 0,
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'models_used': {},
            })
            step_data['calls'] += 1
            step_data['input_tokens'] += input_tokens
            step_data['output_tokens'] += output_tokens
            step_data['total_tokens'] = step_data['input_tokens'] + step_data['output_tokens']

            # Per-model breakdown
            models = step_data['models_used']
            model_key = f"{model}" + (f" @ {base_url}" if base_url else "")
            if model_key not in models:
                models[model_key] = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0}
            models[model_key]['calls'] += 1
            models[model_key]['input_tokens'] += input_tokens
            models[model_key]['output_tokens'] += output_tokens

            data['last_updated'] = datetime.utcnow().isoformat()
            _save(simulation_id, data)

    @staticmethod
    def get_totals(simulation_id: str) -> Dict[str, Any]:
        """Return the full usage record for a simulation, or an empty dict if not found."""
        with _file_lock:
            return _load(simulation_id)

    @staticmethod
    def get_grand_total(simulation_id: str) -> Dict[str, int]:
        """Sum across all steps. Returns dict with input, output, total, calls."""
        data = TokenTracker.get_totals(simulation_id)
        result = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0, 'calls': 0}
        for step_data in data.get('steps', {}).values():
            result['input_tokens'] += step_data.get('input_tokens', 0)
            result['output_tokens'] += step_data.get('output_tokens', 0)
            result['total_tokens'] += step_data.get('total_tokens', 0)
            result['calls'] += step_data.get('calls', 0)
        return result

    @staticmethod
    def reset(simulation_id: str) -> None:
        """Delete the usage record for a simulation (e.g. on rerun)."""
        path = _storage_path(simulation_id)
        with _file_lock:
            if path.exists():
                path.unlink()
