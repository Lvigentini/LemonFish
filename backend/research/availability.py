"""
Centralized availability probing for the research module.

This module exists so the API endpoint can ask "what runners are available?"
without importing each runner individually. The actual probe logic lives on
each runner's is_available() method — this file just iterates and aggregates.

Used by:
    - GET /api/research/availability         (frontend Step 0 picker)
    - The orchestrator's pre-flight check    (before fanning out)
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Dict, List, Optional

logger = logging.getLogger('research.availability')


def detect_docker_mode() -> bool:
    """Best-effort detection of whether we are running inside a container.

    Used by /availability so the frontend can warn the user that CLI runners
    require their host OAuth config to be mounted in (via the
    docker-compose.research.yml overlay).
    """
    # Standard cgroup-based detection (works for most Docker / Podman setups)
    try:
        if os.path.exists('/.dockerenv'):
            return True
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            if 'docker' in content or 'containerd' in content or 'kubepods' in content:
                return True
    except Exception:
        pass
    return False


def which(name: str) -> Optional[str]:
    """Return the absolute path to a CLI tool, or None if not on PATH."""
    return shutil.which(name)


def aggregate_runner_status(runner_names: List[str]) -> Dict[str, dict]:
    """For each runner name in the list, instantiate via the orchestrator's
    registry and call is_available(). Returns a dict keyed by runner name.

    Lazy-imports orchestrator to avoid bootstrap loops.
    """
    from .orchestrator import get_runner

    results: Dict[str, dict] = {}
    for name in runner_names:
        try:
            runner = get_runner(name)
            results[name] = runner.is_available().to_dict()
        except KeyError:
            results[name] = {
                'name': name,
                'available': False,
                'auth_ok': False,
                'reason': f"Runner {name!r} is enabled but no implementation is registered",
                'version': None,
            }
        except Exception as e:
            logger.warning(f"Availability probe for {name} crashed: {e}")
            results[name] = {
                'name': name,
                'available': False,
                'auth_ok': False,
                'reason': f"{type(e).__name__}: {e}",
                'version': None,
            }
    return results
