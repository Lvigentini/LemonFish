"""
OpenAI Codex CLI runner.

Shells out to the locally-installed `codex` CLI in non-interactive mode via
the `codex exec` subcommand. Codex's `exec` mode is documented as the
"run non-interactively" entry point — it executes a single prompt and exits,
which is exactly what the research orchestrator needs.

Verified subcommands and flags (from the openai/codex repository):
    codex exec [--json] "<prompt>"   — non-interactive run
    codex login                       — interactive ChatGPT/API-key login
    codex logout                      — sign out

Auth model:
    Codex supports two paths:
        1. ChatGPT sign-in (Plus/Pro/Business/Edu/Enterprise) — uses ~/.codex
        2. OPENAI_API_KEY env var

We probe via `codex --version` for installation, then `codex login status`
(or fall back to checking the config dir) for auth. Note: the exact auth-
status subcommand may vary across Codex versions; the runner attempts a few
known patterns and falls back gracefully.

When running inside Docker, ~/.codex must be mounted in via the
docker-compose.research.yml overlay (the same as the Claude runner's
~/.claude requirement).

NOTE: This runner has been written from documentation, not exhaustively
tested with a real Codex install. Before relying on it in production, run
the runner's `is_available()` and a smoke `run()` against your local Codex
CLI and update the parsing in this file if the JSON envelope shape differs.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from typing import List, Optional

from ..models import ResearchSummary, SubTopic
from .base import (
    AvailabilityResult,
    CLIRunner,
    ResearchAuthError,
    ResearchRunnerError,
    ResearchTimeoutError,
)

logger = logging.getLogger('research.runner.codex')


CODEX_BIN = 'codex'


def _build_subprocess_env() -> dict:
    """Minimal env passed to the codex subprocess. We deliberately do NOT
    leak our LLM_API_KEY into the CLI's env, but we DO pass through
    OPENAI_API_KEY if the user has set it explicitly (since that is the
    Codex API-key auth path)."""
    keep = ('PATH', 'HOME', 'USER', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM', 'TMPDIR', 'SHELL')
    out = {k: os.environ[k] for k in keep if k in os.environ}
    if 'OPENAI_API_KEY' in os.environ:
        out['OPENAI_API_KEY'] = os.environ['OPENAI_API_KEY']
    if 'HOME' not in out and 'USERPROFILE' in os.environ:
        out['HOME'] = os.environ['USERPROFILE']
    return out


_URL_RE = re.compile(r'https?://[^\s\)\]\>]+')


def _extract_citations(text: str) -> List[str]:
    seen = set()
    out: List[str] = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip('.,;:!?')
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


_USER_PROMPT_INSTRUCTIONS = (
    "You are a research agent for LemonFish, a multi-agent prediction simulation engine. "
    "You will be given a single research sub-topic with specific questions. Use the web "
    "search tools available to you to gather authoritative information and produce a "
    "focused, factual summary that addresses the questions. Requirements:\n"
    "- ~600-1200 words\n"
    "- Concrete: include numbers, dates, named organisations, regulations, products\n"
    "- Cite sources inline using full URLs in parentheses, e.g. (https://example.com/article)\n"
    "- If a question cannot be answered from public sources, say so explicitly\n"
    "- Output: prose only. No code blocks, no tool transcripts, no commentary.\n"
)


class CodexRunner(CLIRunner):
    name = 'codex'

    def __init__(self) -> None:
        self._bin: Optional[str] = None

    # -- availability --------------------------------------------------------

    def is_available(self) -> AvailabilityResult:
        bin_path = shutil.which(CODEX_BIN)
        if not bin_path:
            return AvailabilityResult(
                name=self.name,
                available=False,
                reason=(
                    f"`{CODEX_BIN}` not found on PATH. Install with "
                    f"`npm i -g @openai/codex` or `brew install --cask codex`"
                ),
            )
        self._bin = bin_path

        # Version
        version: Optional[str] = None
        try:
            v = subprocess.run(
                [bin_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                env=_build_subprocess_env(),
            )
            if v.returncode == 0:
                version = (v.stdout or v.stderr or '').strip().split()[0] if (v.stdout or v.stderr).strip() else None
        except Exception as e:
            logger.debug(f"codex --version failed: {e}")

        # Auth check. Codex versions vary on the exact subcommand:
        #   - newer: `codex login status` (returns 0 if logged in)
        #   - older: check for ~/.codex/auth.json existing
        # Try the subcommand first; if that fails, fall back to the config-dir check.
        auth_ok = False
        auth_reason: Optional[str] = None

        try:
            ls = subprocess.run(
                [bin_path, 'login', 'status'],
                capture_output=True,
                text=True,
                timeout=10,
                env=_build_subprocess_env(),
            )
            if ls.returncode == 0:
                auth_ok = True
            else:
                auth_reason = (ls.stderr or ls.stdout or '').strip()[:200]
        except Exception:
            pass

        if not auth_ok:
            # Fallback: API key in env counts as auth
            if 'OPENAI_API_KEY' in os.environ and os.environ['OPENAI_API_KEY'].strip():
                auth_ok = True
                auth_reason = 'using OPENAI_API_KEY env var'
            else:
                # Fallback: look for cached credentials
                home = os.path.expanduser('~')
                candidates = [
                    os.path.join(home, '.codex', 'auth.json'),
                    os.path.join(home, '.codex', 'session.json'),
                    os.path.join(home, '.codex', 'config.json'),
                ]
                for path in candidates:
                    if os.path.exists(path):
                        auth_ok = True
                        auth_reason = f"found credentials at {path}"
                        break

        if not auth_ok:
            return AvailabilityResult(
                name=self.name,
                available=True,
                auth_ok=False,
                reason=auth_reason or 'Not signed in. Run `codex login` to authenticate.',
                version=version,
            )

        return AvailabilityResult(
            name=self.name,
            available=True,
            auth_ok=True,
            reason=auth_reason,
            version=version,
        )

    # -- run -----------------------------------------------------------------

    def run(self, sub_topic: SubTopic, system_prompt: str, timeout: int) -> ResearchSummary:
        if self._bin is None:
            self._bin = shutil.which(CODEX_BIN)
        if not self._bin:
            raise ResearchRunnerError(f"`{CODEX_BIN}` not found on PATH")

        prompt = self._build_prompt(sub_topic, system_prompt)

        # `codex exec --json "<prompt>"` is the documented non-interactive form.
        # Some Codex versions also accept --no-tui or similar; we stick to the
        # documented public surface.
        cmd = [
            self._bin,
            'exec',
            '--json',
            prompt,
        ]

        logger.info(
            f"CodexRunner: launching subprocess for sub-topic {sub_topic.index} "
            f"({sub_topic.topic[:60]!r}), timeout={timeout}s"
        )

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=_build_subprocess_env(),
                cwd=os.path.expanduser('~'),
            )
        except subprocess.TimeoutExpired:
            raise ResearchTimeoutError(
                f"CodexRunner timed out after {timeout}s for sub-topic {sub_topic.index}"
            )
        except FileNotFoundError as e:
            raise ResearchRunnerError(f"CodexRunner: {CODEX_BIN} disappeared from PATH: {e}")

        if proc.returncode != 0:
            stderr_tail = (proc.stderr or '').strip()[-500:]
            stdout_tail = (proc.stdout or '').strip()[-500:]
            combined = (stderr_tail + ' ' + stdout_tail).lower()
            if 'auth' in combined or 'login' in combined or 'unauthor' in combined:
                raise ResearchAuthError(
                    f"CodexRunner authentication failed: {stderr_tail or stdout_tail}"
                )
            raise ResearchRunnerError(
                f"CodexRunner exited {proc.returncode} for sub-topic {sub_topic.index}. "
                f"stderr: {stderr_tail}"
            )

        body = self._parse_codex_output(proc.stdout)
        if not body:
            raise ResearchRunnerError(
                f"CodexRunner produced no parseable output for sub-topic {sub_topic.index}. "
                f"Raw stdout (first 500 chars): {(proc.stdout or '')[:500]}"
            )

        return ResearchSummary(
            sub_topic_index=sub_topic.index,
            runner=self.name,
            body=body,
            citations=_extract_citations(body),
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _build_prompt(sub_topic: SubTopic, system_prompt: str) -> str:
        questions_block = '\n'.join(f"- {q}" for q in sub_topic.questions) or '- (no specific questions provided)'
        return (
            f"{_USER_PROMPT_INSTRUCTIONS}\n\n"
            f"Additional instructions from the orchestrator:\n{system_prompt}\n\n"
            f"=== TASK ===\n"
            f"Research sub-topic: {sub_topic.topic}\n\n"
            f"Questions to answer:\n{questions_block}\n\n"
            f"Begin research now and produce the summary."
        )

    @staticmethod
    def _parse_codex_output(stdout: str) -> str:
        """Parse `codex exec --json` output.

        The exact JSON envelope shape varies by Codex version. We try several
        known patterns:

            1. Single JSON object: {"output": "...", "result": "...", ...}
            2. JSONL stream: each line a JSON event; the final assistant message
               has type "message" or "assistant_response"
            3. Plain text fallback: just use the raw stdout

        Returns the extracted body, or '' if nothing parseable was found.
        """
        if not stdout:
            return ''

        # Try single-object parse first
        try:
            obj = json.loads(stdout)
            if isinstance(obj, dict):
                for key in ('output', 'result', 'response', 'message', 'text', 'final'):
                    val = obj.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
        except json.JSONDecodeError:
            pass

        # Try line-by-line JSON event stream
        message_parts: List[str] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = (event.get('type') or '').lower()
            if event_type in ('message', 'assistant_message', 'assistant_response', 'final', 'text'):
                content = event.get('content') or event.get('text') or event.get('message')
                if isinstance(content, str):
                    message_parts.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get('text'), str):
                            message_parts.append(part['text'])
                        elif isinstance(part, str):
                            message_parts.append(part)

        if message_parts:
            return '\n'.join(message_parts).strip()

        # Last resort: raw stdout
        return stdout.strip()
