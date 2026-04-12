"""
Claude Code CLI runner.

Shells out to the locally-installed `claude` CLI in non-interactive print
mode (`-p`). Claude Code has WebSearch and WebFetch built in, so a single
prompt can drive the whole research-for-one-sub-topic loop.

Verified against `claude --version` 2.1.x and `claude auth status`. Flags
used:

    claude -p "<user prompt>"
        --output-format json            (structured output)
        --append-system-prompt "<sys>"  (add LemonFish-specific instructions
                                         on top of Claude Code's defaults)
        --tools "WebSearch,WebFetch"    (restrict the tool surface)
        --permission-mode bypassPermissions
                                        (no interactive prompts; we trust
                                         our own system prompt to gate)
        --no-session-persistence        (don't pollute the user's session list)
        --disable-slash-commands        (skills don't help research)
        --bare                          (skip auto-memory, plugins, etc — keep
                                         the runner cheap and reproducible)

Auth is taken from the user's Claude Code OAuth (~/.claude). When running
inside Docker, that directory must be mounted in via the
docker-compose.research.yml overlay.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from typing import List, Optional

from .. import config as research_config
from ..models import ResearchSummary, SubTopic
from .base import (
    AvailabilityResult,
    CLIRunner,
    ResearchAuthError,
    ResearchRunnerError,
    ResearchTimeoutError,
)

logger = logging.getLogger('research.runner.claude')


CLAUDE_BIN = 'claude'

# A minimal env passed to the subprocess. We deliberately strip the parent
# process env so the CLI doesn't see our LLM_API_KEY etc — Claude Code uses
# its own OAuth credentials from ~/.claude, not env vars.
def _build_subprocess_env() -> dict:
    keep = ('PATH', 'HOME', 'USER', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM', 'TMPDIR', 'SHELL')
    out = {k: os.environ[k] for k in keep if k in os.environ}
    # Claude Code reads its own config from $HOME/.claude — make sure HOME is set
    if 'HOME' not in out and 'USERPROFILE' in os.environ:
        out['HOME'] = os.environ['USERPROFILE']
    return out


# URL extraction for citation harvesting from the runner's stdout
_URL_RE = re.compile(r'https?://[^\s\)\]\>]+')


def _extract_citations(text: str) -> List[str]:
    """Pull URLs out of the prose. De-duplicates while preserving order."""
    seen = set()
    out: List[str] = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip('.,;:!?')
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


# System prompt appended on top of Claude Code's defaults
_APPEND_SYSTEM_PROMPT = (
    "You are a research agent for LemonFish, a multi-agent prediction simulation engine. "
    "You will be given a single research sub-topic with specific questions. Your job is to "
    "use the WebSearch and WebFetch tools to gather authoritative information and produce "
    "a focused, factual summary that addresses the questions. Requirements:\n"
    "- ~600-1200 words\n"
    "- Concrete: include numbers, dates, named organisations, regulations, products\n"
    "- Cite sources inline using full URLs in parentheses, e.g. (https://example.com/article)\n"
    "- If a question cannot be answered from public sources, say so explicitly\n"
    "- Output format: structured prose only. No code blocks, no tool transcripts.\n"
    "- Do not editorialise or speculate beyond what the sources support.\n"
    "When you are done, output the final summary as your message — nothing else."
)


class ClaudeRunner(CLIRunner):
    name = 'claude'

    def __init__(self) -> None:
        self._bin: Optional[str] = None  # cached path to the CLI

    # -- availability --------------------------------------------------------

    def is_available(self) -> AvailabilityResult:
        bin_path = shutil.which(CLAUDE_BIN)
        if not bin_path:
            return AvailabilityResult(
                name=self.name,
                available=False,
                reason=f"`{CLAUDE_BIN}` not found on PATH. Install Claude Code from https://docs.claude.com/claude-code",
            )
        self._bin = bin_path

        # Get version
        try:
            version_proc = subprocess.run(
                [bin_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                env=_build_subprocess_env(),
            )
            version = (version_proc.stdout or version_proc.stderr or '').strip().split()[0]
        except Exception as e:
            version = None
            logger.debug(f"claude --version failed: {e}")

        # Check auth status
        try:
            auth_proc = subprocess.run(
                [bin_path, 'auth', 'status'],
                capture_output=True,
                text=True,
                timeout=10,
                env=_build_subprocess_env(),
            )
        except subprocess.TimeoutExpired:
            return AvailabilityResult(
                name=self.name,
                available=True,
                auth_ok=False,
                reason='`claude auth status` timed out after 10s',
                version=version,
            )
        except Exception as e:
            return AvailabilityResult(
                name=self.name,
                available=True,
                auth_ok=False,
                reason=f"`claude auth status` failed: {type(e).__name__}: {e}",
                version=version,
            )

        if auth_proc.returncode != 0:
            return AvailabilityResult(
                name=self.name,
                available=True,
                auth_ok=False,
                reason=(auth_proc.stderr or auth_proc.stdout or 'auth check returned non-zero').strip()[:200],
                version=version,
            )

        # Parse JSON; Claude Code 2.x emits structured output
        try:
            payload = json.loads(auth_proc.stdout)
        except json.JSONDecodeError:
            # Fall back to a simple substring check
            text = (auth_proc.stdout or '').lower()
            if 'logged' in text and 'in' in text:
                return AvailabilityResult(name=self.name, available=True, auth_ok=True, version=version)
            return AvailabilityResult(
                name=self.name,
                available=True,
                auth_ok=False,
                reason='Could not parse `claude auth status` output',
                version=version,
            )

        if not payload.get('loggedIn'):
            return AvailabilityResult(
                name=self.name,
                available=True,
                auth_ok=False,
                reason='Not logged in. Run `claude auth login` to authenticate.',
                version=version,
            )

        return AvailabilityResult(
            name=self.name,
            available=True,
            auth_ok=True,
            version=version,
        )

    # -- run -----------------------------------------------------------------

    def run(self, sub_topic: SubTopic, system_prompt: str, timeout: int) -> ResearchSummary:
        # Lazy availability check (cheap if already cached)
        if self._bin is None:
            self._bin = shutil.which(CLAUDE_BIN)
        if not self._bin:
            raise ResearchRunnerError(f"`{CLAUDE_BIN}` not found on PATH")

        user_prompt = self._build_user_prompt(sub_topic)

        # Combine the orchestrator-provided system prompt with our Claude-specific one.
        # The orchestrator's prompt is the "what shape of output" instruction; our
        # appended one is the "how to use Claude Code's tools" instruction.
        append_system = _APPEND_SYSTEM_PROMPT + "\n\n" + system_prompt

        cmd = [
            self._bin,
            '-p',
            user_prompt,
            '--output-format', 'json',
            '--append-system-prompt', append_system,
            '--tools', 'WebSearch,WebFetch',
            '--permission-mode', 'bypassPermissions',
            '--no-session-persistence',
            '--disable-slash-commands',
            '--bare',
        ]

        logger.info(
            f"ClaudeRunner: launching subprocess for sub-topic {sub_topic.index} "
            f"({sub_topic.topic[:60]!r}), timeout={timeout}s"
        )

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=_build_subprocess_env(),
                # Run from the user's home directory so the CLI doesn't try to
                # auto-discover a CLAUDE.md from a project we don't care about.
                cwd=os.path.expanduser('~'),
            )
        except subprocess.TimeoutExpired:
            raise ResearchTimeoutError(
                f"ClaudeRunner timed out after {timeout}s for sub-topic {sub_topic.index}"
            )
        except FileNotFoundError as e:
            raise ResearchRunnerError(f"ClaudeRunner: {CLAUDE_BIN} disappeared from PATH: {e}")

        if proc.returncode != 0:
            stderr_tail = (proc.stderr or '').strip()[-500:]
            stdout_tail = (proc.stdout or '').strip()[-500:]
            # Detect auth failures specifically — they're recoverable by the user
            combined = (stderr_tail + ' ' + stdout_tail).lower()
            if 'auth' in combined and ('login' in combined or 'expired' in combined or 'not logged' in combined):
                raise ResearchAuthError(
                    f"ClaudeRunner authentication failed: {stderr_tail or stdout_tail}"
                )
            raise ResearchRunnerError(
                f"ClaudeRunner exited {proc.returncode} for sub-topic {sub_topic.index}. "
                f"stderr: {stderr_tail}"
            )

        # The --output-format json schema for `claude -p ... --output-format json`
        # returns an envelope like:
        #     {"type": "result", "subtype": "...", "result": "<final assistant message>", ...}
        # We try to parse it as JSON; if that fails, treat the whole stdout as the body.
        body = ''
        try:
            payload = json.loads(proc.stdout)
            if isinstance(payload, dict):
                # Common fields seen in Claude Code 2.x output
                for key in ('result', 'response', 'text', 'message', 'output'):
                    val = payload.get(key)
                    if isinstance(val, str) and val.strip():
                        body = val.strip()
                        break
                # Some versions emit a list of content parts
                if not body and isinstance(payload.get('content'), list):
                    parts = []
                    for part in payload['content']:
                        if isinstance(part, dict) and isinstance(part.get('text'), str):
                            parts.append(part['text'])
                        elif isinstance(part, str):
                            parts.append(part)
                    body = '\n'.join(parts).strip()
        except json.JSONDecodeError:
            body = ''

        # Last-resort fallback: use the raw stdout
        if not body:
            body = (proc.stdout or '').strip()

        if not body:
            raise ResearchRunnerError(
                f"ClaudeRunner produced no output for sub-topic {sub_topic.index}"
            )

        citations = _extract_citations(body)

        return ResearchSummary(
            sub_topic_index=sub_topic.index,
            runner=self.name,
            body=body,
            citations=citations,
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(sub_topic: SubTopic) -> str:
        questions_block = '\n'.join(f"- {q}" for q in sub_topic.questions) or '- (no specific questions provided)'
        return (
            f"Research sub-topic: {sub_topic.topic}\n\n"
            f"Specific questions to answer:\n{questions_block}\n\n"
            f"Use WebSearch and WebFetch as needed. Produce a focused, factual summary "
            f"as described in your instructions. Do not add any commentary outside the summary."
        )
