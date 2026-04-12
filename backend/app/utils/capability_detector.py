"""
LLM Provider Capability Detection (Phase 5)

Tests each (base_url, model) combo for feature support and caches the
results on disk. The main use case is distinguishing providers that
support OpenAI's `response_format={"type": "json_object"}` (OpenAI,
Google Gemini, Groq, OpenRouter most models) from those that don't
(Anthropic Claude, xAI Grok some models).

Detection works by sending a tiny test message and inspecting either
the response format or the error. Results are cached in
`backend/uploads/capability_cache.json` with a configurable TTL
(default 7 days).

Public API:
    from .capability_detector import supports_json_mode, probe_capabilities

    if supports_json_mode(api_key, base_url, model):
        # use response_format
    else:
        # use prompt-based JSON extraction
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

_cache_lock = threading.Lock()
_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / 'uploads' / 'capability_cache.json'
_DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def _cache_key(base_url: str, model: str) -> str:
    """Build a cache key. API keys are NOT included — capability is a provider property."""
    return f"{base_url}||{model}"


def _load_cache() -> Dict[str, Any]:
    if not _CACHE_PATH.exists():
        return {}
    try:
        with open(_CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read capability cache: {e}")
        return {}


def _save_cache(data: Dict[str, Any]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CACHE_PATH.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(_CACHE_PATH)


def _is_fresh(entry: Dict[str, Any], ttl: int) -> bool:
    checked_at = entry.get('checked_at', 0)
    return (time.time() - checked_at) < ttl


def probe_capabilities(
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Probe a (base_url, model) pair and return a capability record.

    Returns a dict with keys:
        base_url, model, checked_at, supports_json_mode, supports_response_format,
        json_mode_error, basic_chat_works, error
    """
    result: Dict[str, Any] = {
        'base_url': base_url,
        'model': model,
        'checked_at': time.time(),
        'supports_json_mode': False,
        'supports_response_format': False,
        'json_mode_error': None,
        'basic_chat_works': False,
        'error': None,
    }

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    # Test 1: basic chat works at all
    # Use a generous max_tokens because reasoning models (Gemini 3, o1, etc.)
    # consume internal thinking tokens before emitting visible output.
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Say OK."},
            ],
            max_tokens=500,
            temperature=0,
        )
        result['basic_chat_works'] = bool(
            response.choices and (response.choices[0].message.content or '').strip()
        )
    except Exception as e:
        result['error'] = f"basic chat failed: {type(e).__name__}: {str(e)[:200]}"
        return result

    # Test 2: JSON mode via response_format
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": 'Return a JSON object like {"status": "ok"}'},
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0,
        )
        content = (response.choices[0].message.content or '').strip() if response.choices else ''
        # Even if the provider accepted response_format, verify it returned parseable JSON
        if content:
            try:
                # Strip any markdown fences just in case
                stripped = content.replace('```json', '').replace('```', '').strip()
                json.loads(stripped)
                result['supports_json_mode'] = True
                result['supports_response_format'] = True
            except json.JSONDecodeError:
                result['supports_response_format'] = True  # accepted the param but didn't produce JSON
                result['supports_json_mode'] = False
        else:
            # Empty content — most likely hit max_tokens during reasoning
            result['supports_response_format'] = True  # provider accepted the parameter
            result['json_mode_error'] = 'empty content (possibly hit max_tokens before output)'
    except Exception as e:
        err_msg = str(e)[:300]
        result['json_mode_error'] = f"{type(e).__name__}: {err_msg}"
        result['supports_json_mode'] = False
        result['supports_response_format'] = False

    return result


def _get_or_probe(
    api_key: str,
    base_url: str,
    model: str,
    ttl: int = _DEFAULT_TTL_SECONDS,
    force: bool = False,
) -> Dict[str, Any]:
    """Return the cached capability record, probing fresh if stale or missing."""
    key = _cache_key(base_url, model)
    with _cache_lock:
        cache = _load_cache()
        entry = cache.get(key)
        if entry and not force and _is_fresh(entry, ttl):
            return entry

    # Probe outside the lock (network I/O)
    logger.info(f"Probing capabilities for {model} @ {base_url}")
    record = probe_capabilities(api_key=api_key, base_url=base_url, model=model)

    with _cache_lock:
        cache = _load_cache()
        cache[key] = record
        _save_cache(cache)

    return record


def supports_json_mode(
    api_key: str,
    base_url: str,
    model: str,
    ttl: int = _DEFAULT_TTL_SECONDS,
) -> bool:
    """Quick check: does this (base_url, model) support response_format=json_object?"""
    try:
        record = _get_or_probe(api_key, base_url, model, ttl=ttl)
        return bool(record.get('supports_json_mode', False))
    except Exception as e:
        logger.warning(f"Capability check failed, assuming JSON mode works: {e}")
        return True  # optimistic fallback


def get_all_cached() -> Dict[str, Any]:
    """Return the entire capability cache (for inspection/UI)."""
    with _cache_lock:
        return _load_cache()


def clear_cache() -> None:
    with _cache_lock:
        if _CACHE_PATH.exists():
            _CACHE_PATH.unlink()


def force_refresh(api_key: str, base_url: str, model: str) -> Dict[str, Any]:
    """Force a fresh probe, overwriting the cache."""
    return _get_or_probe(api_key, base_url, model, force=True)
