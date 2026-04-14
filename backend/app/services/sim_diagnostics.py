"""
Simulation diagnostics — parse OASIS simulation.log + SQLite activity so
the frontend can show meaningful warnings when a run completes but
produces too little data for reporting.

This module is read-only. It never mutates sim state; it just introspects
what the runner left behind on disk.
"""

import os
import re
import sqlite3
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
import json

from ..config import Config

# Patterns we look for in simulation.log. Order matters — more specific
# patterns go first so they capture before the generic catch-alls.
_ERROR_PATTERNS = [
    ('rate_limit_exhausted', re.compile(r'Rate limit exhausted after \d+ attempts', re.I)),
    ('rate_limit_retry',     re.compile(r'Rate limit hit \(attempt', re.I)),
    ('model_error',          re.compile(r'Error processing with model', re.I)),
    ('api_404',              re.compile(r'\b404\b|Not Found|model.*not found', re.I)),
    ('api_429',              re.compile(r'\b429\b|quota.*exceeded|ResourceExhausted', re.I)),
    ('api_5xx',              re.compile(r'\b5\d\d\b'))  # crude
]

# Activity floor below which a sim is considered "too empty to report on".
# Expressed as a fraction of (agents × rounds) expected actions. The
# report endpoint uses this to refuse gracefully.
MIN_ACTIVITY_FRACTION = 0.1

# Absolute minimum regardless of fraction — a sim with 2 agents × 1 round
# is not expected to hit the fraction-based floor, but it still needs at
# least a handful of actions for the ReACT agent to have anything to say.
MIN_ABSOLUTE_ACTIONS = 10


@dataclass
class SimActivity:
    posts: int = 0
    comments: int = 0
    traces: int = 0
    actions_total: int = 0      # from run_state.json if present
    actions_twitter: int = 0
    actions_reddit: int = 0
    likes: int = 0
    follows: int = 0


@dataclass
class SimErrorSummary:
    counts: Dict[str, int]      # pattern_key -> count
    total: int
    sample_lines: List[str]     # last N raw log lines that matched any pattern
    log_tail: List[str]         # last N raw log lines (regardless of match)


@dataclass
class SimDiagnostics:
    simulation_id: str
    sim_dir: str
    log_exists: bool
    activity: SimActivity
    errors: SimErrorSummary
    expected_min_actions: int
    is_reportable: bool
    blocker: Optional[str]      # human-readable reason if not reportable
    warnings: List[str]         # non-fatal flags the UI should surface

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def _sim_dir(simulation_id: str) -> str:
    return os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)


def _read_run_state(sim_dir: str) -> Dict[str, Any]:
    path = os.path.join(sim_dir, 'run_state.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _read_sim_state(sim_dir: str) -> Dict[str, Any]:
    path = os.path.join(sim_dir, 'state.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _db_counts(sim_dir: str, platform: str) -> Dict[str, int]:
    """Query post/comment/like/follow counts from a platform's SQLite DB.

    Returns zeros when the DB is missing or the schema doesn't match —
    we never want diagnostics to 500 the endpoint.
    """
    db = os.path.join(sim_dir, f'{platform}_simulation.db')
    out = {'posts': 0, 'comments': 0, 'likes': 0, 'follows': 0, 'traces': 0}
    if not os.path.exists(db):
        return out
    try:
        conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2)
        cur = conn.cursor()
        for key, sql in [
            ('posts',    "SELECT COUNT(*) FROM post"),
            ('comments', "SELECT COUNT(*) FROM comment"),
            ('likes',    "SELECT COUNT(*) FROM like"),
            ('follows',  "SELECT COUNT(*) FROM follow"),
            ('traces',   "SELECT COUNT(*) FROM trace"),
        ]:
            try:
                cur.execute(sql)
                out[key] = cur.fetchone()[0] or 0
            except sqlite3.Error:
                pass
        conn.close()
    except sqlite3.Error:
        pass
    return out


def _parse_log(sim_dir: str, tail_lines: int = 40) -> SimErrorSummary:
    path = os.path.join(sim_dir, 'simulation.log')
    if not os.path.exists(path):
        return SimErrorSummary(counts={}, total=0, sample_lines=[], log_tail=[])

    counts: Dict[str, int] = {}
    matched_lines: List[str] = []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            # Efficient-ish tail: read the whole thing. Sim logs are small.
            all_lines = f.readlines()
    except Exception:
        return SimErrorSummary(counts={}, total=0, sample_lines=[], log_tail=[])

    for line in all_lines:
        line_stripped = line.rstrip('\n')
        for key, pat in _ERROR_PATTERNS:
            if pat.search(line_stripped):
                counts[key] = counts.get(key, 0) + 1
                matched_lines.append(line_stripped)
                break  # each line counted once

    # Keep the last N matched lines as samples.
    sample_lines = matched_lines[-20:]
    log_tail = [l.rstrip('\n') for l in all_lines[-tail_lines:]]
    total = sum(counts.values())
    return SimErrorSummary(counts=counts, total=total, sample_lines=sample_lines, log_tail=log_tail)


def collect(simulation_id: str) -> SimDiagnostics:
    """Gather activity + error summary for a simulation.

    Never raises. On missing data, returns a diagnostics object with
    zeroed counts and blocker='missing_data' so the UI can show an
    appropriate message.
    """
    sim_dir = _sim_dir(simulation_id)
    if not os.path.isdir(sim_dir):
        return SimDiagnostics(
            simulation_id=simulation_id,
            sim_dir=sim_dir,
            log_exists=False,
            activity=SimActivity(),
            errors=SimErrorSummary(counts={}, total=0, sample_lines=[], log_tail=[]),
            expected_min_actions=0,
            is_reportable=False,
            blocker='missing_sim_dir',
            warnings=[],
        )

    run_state = _read_run_state(sim_dir)
    sim_state = _read_sim_state(sim_dir)

    twitter = _db_counts(sim_dir, 'twitter')
    reddit = _db_counts(sim_dir, 'reddit')

    activity = SimActivity(
        posts=twitter['posts'] + reddit['posts'],
        comments=twitter['comments'] + reddit['comments'],
        traces=twitter['traces'] + reddit['traces'],
        actions_total=int(run_state.get('total_actions_count') or 0),
        actions_twitter=int(run_state.get('twitter_actions_count') or 0),
        actions_reddit=int(run_state.get('reddit_actions_count') or 0),
        likes=twitter['likes'] + reddit['likes'],
        follows=twitter['follows'] + reddit['follows'],
    )

    errors = _parse_log(sim_dir)

    # Expected-action floor.
    agents = int(sim_state.get('profiles_count') or sim_state.get('entities_count') or 0)
    total_rounds = int(run_state.get('total_rounds') or 0)
    expected_min = max(
        MIN_ABSOLUTE_ACTIONS,
        int(agents * total_rounds * MIN_ACTIVITY_FRACTION)
    )

    # Reportability + blocker classification.
    warnings: List[str] = []
    blocker: Optional[str] = None
    is_reportable = True

    if activity.actions_total == 0 and activity.posts == 0:
        is_reportable = False
        blocker = 'no_activity'
    elif activity.actions_total < expected_min:
        is_reportable = False
        blocker = 'insufficient_activity'

    # Warnings even when reportable.
    if errors.counts.get('rate_limit_exhausted', 0) > 0:
        warnings.append('llm_rate_limits')
    if errors.counts.get('api_404', 0) > 0:
        warnings.append('llm_404_errors')
    if errors.counts.get('api_429', 0) > 0:
        warnings.append('llm_429_errors')
    if activity.posts > 0 and activity.comments == 0:
        warnings.append('no_discourse')
    if activity.actions_total < expected_min * 2 and is_reportable:
        warnings.append('low_activity')

    return SimDiagnostics(
        simulation_id=simulation_id,
        sim_dir=sim_dir,
        log_exists=os.path.exists(os.path.join(sim_dir, 'simulation.log')),
        activity=activity,
        errors=errors,
        expected_min_actions=expected_min,
        is_reportable=is_reportable,
        blocker=blocker,
        warnings=warnings,
    )
