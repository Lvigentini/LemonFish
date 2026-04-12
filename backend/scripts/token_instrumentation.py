"""
Subprocess token usage instrumentation.

Monkey-patches the OpenAI SDK's chat.completions.create() to intercept
responses and write token usage to the same shared JSON file used by the
parent process's TokenTracker.

Called from the subprocess (run_*_simulation.py) at startup via:
    from token_instrumentation import install
    install()

Reads these env vars:
    MIROFISH_SIMULATION_ID — which simulation to attribute usage to
    MIROFISH_TOKEN_STEP    — which pipeline step (default: simulation)
    LLM_SIMULATION_MODEL / LLM_MODEL_NAME — for labelling

No-ops if MIROFISH_SIMULATION_ID is not set.
"""

import json
import os
import sys
import threading
from pathlib import Path
from datetime import datetime

_lock = threading.Lock()
_installed = False


def _storage_path(simulation_id: str) -> Path:
    # Must match backend/app/utils/token_tracker.py::_storage_path
    # backend/scripts/ is at the same level as backend/app/, so uploads is at ../uploads relative to scripts.
    scripts_dir = Path(__file__).resolve().parent
    uploads_dir = scripts_dir.parent / 'uploads' / 'token_usage'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir / f'{simulation_id}.json'


def _load(simulation_id: str) -> dict:
    path = _storage_path(simulation_id)
    if not path.exists():
        return {
            'simulation_id': simulation_id,
            'created_at': datetime.utcnow().isoformat(),
            'steps': {},
        }
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            'simulation_id': simulation_id,
            'created_at': datetime.utcnow().isoformat(),
            'steps': {},
        }


def _save(simulation_id: str, data: dict) -> None:
    path = _storage_path(simulation_id)
    tmp = path.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _record(input_tokens: int, output_tokens: int, model: str, base_url: str) -> None:
    sim_id = os.environ.get('MIROFISH_SIMULATION_ID')
    if not sim_id:
        return
    step = os.environ.get('MIROFISH_TOKEN_STEP', 'simulation')
    with _lock:
        data = _load(sim_id)
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
        models = step_data['models_used']
        key = f"{model}" + (f" @ {base_url}" if base_url else "")
        if key not in models:
            models[key] = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0}
        models[key]['calls'] += 1
        models[key]['input_tokens'] += input_tokens
        models[key]['output_tokens'] += output_tokens
        data['last_updated'] = datetime.utcnow().isoformat()
        _save(sim_id, data)


def install() -> None:
    """Monkey-patch openai.resources.chat.completions.Completions.create.

    Safe to call multiple times; only patches once per process.
    """
    global _installed
    if _installed:
        return

    sim_id = os.environ.get('MIROFISH_SIMULATION_ID')
    if not sim_id:
        # Nothing to track; silently skip
        return

    try:
        from openai.resources.chat.completions import Completions
    except ImportError:
        print('[token_instrumentation] openai SDK not available; skipping', file=sys.stderr)
        return

    original_create = Completions.create

    def wrapped_create(self, *args, **kwargs):
        response = original_create(self, *args, **kwargs)
        try:
            usage = getattr(response, 'usage', None)
            if usage is not None:
                input_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                output_tokens = getattr(usage, 'completion_tokens', 0) or 0
                model = kwargs.get('model', '') or getattr(response, 'model', '')
                base_url = str(self._client.base_url) if hasattr(self, '_client') else ''
                _record(input_tokens, output_tokens, model, base_url)
        except Exception as e:
            # Never let tracking break the actual LLM call
            print(f'[token_instrumentation] record failed (non-fatal): {e}', file=sys.stderr)
        return response

    Completions.create = wrapped_create
    _installed = True
    print(f'[token_instrumentation] installed for simulation_id={sim_id}', file=sys.stderr)
