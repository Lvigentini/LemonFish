"""
Moonshot Kimi CLI runner.

Shells out to the locally-installed `kimi` CLI (kimi-cli from Moonshot AI).
Kimi CLI is the most beta of the three CLI runners — its non-interactive /
unattended-mode flags are less well documented than Claude Code or Codex.
This runner attempts the most likely invocation patterns and falls back
gracefully when they don't match.

Probable invocation pattern (verify with `kimi --help` on your install):
    kimi -p "<prompt>"            — print mode (similar to claude -p)
    kimi run "<prompt>"           — alternate run subcommand
    echo "<prompt>" | kimi        — stdin pipe

Auth model:
    Kimi CLI uses an interactive `/login` command from inside its REPL,
    storing credentials in ~/.config/kimi or similar. There is no documented
    `kimi auth status` equivalent at the time of writing — we fall back to
    a config-dir presence check.

When running inside Docker, the user's Kimi config dir must be mounted in
via the docker-compose.research.yml overlay.

NOTE: Kimi CLI is the least mature integration in this module. Before
relying on it, run `kimi --help` and update the `_INVOCATION_TEMPLATES`
list and `_KIMI_CONFIG_DIRS` list in this file to match the actual flags
and config locations of the version installed on your system.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from typing import List, Optional, Tuple

from ..models import ResearchSummary, SubTopic
from .base import (
    AvailabilityResult,
    CLIRunner,
    ResearchAuthError,
    ResearchRunnerError,
    ResearchTimeoutError,
)

logger = logging.getLogger('research.runner.kimi')


KIMI_BIN = 'kimi'

# Candidate config directories — checked in order to detect whether the user
# has authenticated. Update to match your install if neither matches.
_KIMI_CONFIG_DIRS = [
    os.path.expanduser('~/.config/kimi'),
    os.path.expanduser('~/.kimi'),
    os.path.expanduser('~/Library/Application Support/kimi'),
]

# Candidate invocation patterns. The runner tries the first one whose return
# code is 0; subsequent attempts are skipped. Each entry is a (description,
# argv-template) pair. {prompt} is substituted with the full research prompt.
_INVOCATION_TEMPLATES: List[Tuple[str, List[str]]] = [
    ('print-mode -p',     ['-p', '{prompt}']),
    ('run subcommand',    ['run', '{prompt}']),
    ('exec subcommand',   ['exec', '{prompt}']),
]


def _build_subprocess_env() -> dict:
    keep = ('PATH', 'HOME', 'USER', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM', 'TMPDIR', 'SHELL')
    out = {k: os.environ[k] for k in keep if k in os.environ}
    # Some Kimi CLI versions look for MOONSHOT_API_KEY as an alternative auth
    if 'MOONSHOT_API_KEY' in os.environ:
        out['MOONSHOT_API_KEY'] = os.environ['MOONSHOT_API_KEY']
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
    "You will be given a single research sub-topic with specific questions. Use any web "
    "search tools available to you to gather authoritative information and produce a "
    "focused, factual summary that addresses the questions. Requirements:\n"
    "- ~600-1200 words\n"
    "- Concrete: include numbers, dates, named organisations, regulations, products\n"
    "- Cite sources inline using full URLs in parentheses, e.g. (https://example.com/article)\n"
    "- If a question cannot be answered from public sources, say so explicitly\n"
    "- Output: prose only. No code blocks, no tool transcripts, no commentary.\n"
)


class KimiRunner(CLIRunner):
    name = 'kimi'

    def __init__(self) -> None:
        self._bin: Optional[str] = None
        # Cached invocation template index after first successful run
        self._working_template: Optional[List[str]] = None

    # -- availability --------------------------------------------------------

    def is_available(self) -> AvailabilityResult:
        bin_path = shutil.which(KIMI_BIN)
        if not bin_path:
            return AvailabilityResult(
                name=self.name,
                available=False,
                reason=(
                    f"`{KIMI_BIN}` not found on PATH. Install from "
                    f"https://github.com/MoonshotAI/kimi-cli"
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
            if v.returncode == 0 and (v.stdout or v.stderr):
                version = (v.stdout or v.stderr).strip().split()[0]
        except Exception as e:
            logger.debug(f"kimi --version failed: {e}")

        # Auth check via config dir presence
        auth_ok = False
        auth_reason: Optional[str] = None
        for cfg_dir in _KIMI_CONFIG_DIRS:
            if os.path.isdir(cfg_dir) and os.listdir(cfg_dir):
                auth_ok = True
                auth_reason = f"found config at {cfg_dir}"
                break

        if not auth_ok and os.environ.get('MOONSHOT_API_KEY', '').strip():
            auth_ok = True
            auth_reason = 'using MOONSHOT_API_KEY env var'

        if not auth_ok:
            return AvailabilityResult(
                name=self.name,
                available=True,
                auth_ok=False,
                reason='No Kimi CLI config found. Run `kimi` and `/login` to authenticate.',
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
            self._bin = shutil.which(KIMI_BIN)
        if not self._bin:
            raise ResearchRunnerError(f"`{KIMI_BIN}` not found on PATH")

        prompt = self._build_prompt(sub_topic, system_prompt)

        # Try cached working template first; otherwise iterate through candidates
        candidates = (
            [('cached', self._working_template)]
            if self._working_template is not None
            else list(_INVOCATION_TEMPLATES)
        )

        last_error: Optional[Exception] = None
        for description, template in candidates:
            cmd = [self._bin] + [arg.replace('{prompt}', prompt) for arg in template]
            logger.info(
                f"KimiRunner: trying {description} for sub-topic {sub_topic.index} "
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
                    f"KimiRunner timed out after {timeout}s for sub-topic {sub_topic.index}"
                )
            except FileNotFoundError as e:
                raise ResearchRunnerError(f"KimiRunner: {KIMI_BIN} disappeared: {e}")

            if proc.returncode == 0 and (proc.stdout or '').strip():
                self._working_template = template  # cache for next call
                body = (proc.stdout or '').strip()
                return ResearchSummary(
                    sub_topic_index=sub_topic.index,
                    runner=self.name,
                    body=body,
                    citations=_extract_citations(body),
                )

            stderr_tail = (proc.stderr or '').strip()[-300:]
            combined = ((proc.stderr or '') + ' ' + (proc.stdout or '')).lower()
            if 'auth' in combined or 'login' in combined:
                raise ResearchAuthError(
                    f"KimiRunner authentication failed: {stderr_tail}"
                )
            last_error = RuntimeError(
                f"{description} returned {proc.returncode}: {stderr_tail or '<empty>'}"
            )
            logger.debug(f"KimiRunner: template {description} failed: {last_error}")

        raise ResearchRunnerError(
            f"KimiRunner: no invocation pattern worked for sub-topic {sub_topic.index}. "
            f"Last error: {last_error}. "
            f"Update _INVOCATION_TEMPLATES in {__file__} to match your kimi-cli version."
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
