"""
API fallback runner — uses LLMClient + DuckDuckGo to research a sub-topic
without requiring any local CLI tool to be installed.

This is the always-available baseline. The orchestrator falls back to this
when the user picks `runner_choice=api`, when no CLI runners are available,
or when a CLI runner fails partway through.

Algorithm per sub-topic:
    1. Build a search query from the sub-topic title and questions
    2. DDG search → top N candidate URLs
    3. Fetch up to FETCH_TOP URLs (with timeout, html→text)
    4. Pass the source material + sub-topic to the LLM (Plan-step model)
       and ask it to produce a structured summary with inline citations
    5. Return the summary, with citation URLs in the order they appeared

The LLM is reused from the existing app.utils.llm_client.LLMClient (which
already has retry/backoff and fallback model support from earlier phases).
This runner does not need its own LLM client — it just constructs one with
the per-step config from Phase 2.
"""

from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Tuple

from .. import config as research_config
from ..models import ResearchSummary, SubTopic
from ..search import ddg as search_ddg
from .base import (
    AvailabilityResult,
    CLIRunner,
    ResearchAuthError,
    ResearchRunnerError,
    ResearchTimeoutError,
)

logger = logging.getLogger(__name__)


def _import_llm_client():
    """Lazy import so this module can be inspected without the full app env."""
    from app.utils.llm_client import LLMClient
    from app.config import Config
    return LLMClient, Config


def _import_urllib():
    import urllib.request
    import urllib.error
    return urllib.request, urllib.error


# ---------------------------------------------------------------------------
# HTML fetch + cleanup
# ---------------------------------------------------------------------------


_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


def _strip_html(html: str) -> str:
    """Cheap HTML→text. Good enough for LLM consumption — we don't need a
    full DOM parser, we just need readable text."""
    # Remove script/style blocks entirely
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = _HTML_TAG_RE.sub(' ', html)
    # Decode common entities without depending on html.unescape (which would work but
    # adds minimal value over the most common ones)
    import html as html_lib
    text = html_lib.unescape(text)
    return _WHITESPACE_RE.sub(' ', text).strip()


def _fetch_url(url: str, timeout: int = 15, max_chars: int = 20000) -> Optional[str]:
    """Best-effort fetch of a URL → cleaned text. Returns None on any failure."""
    urllib_request, urllib_error = _import_urllib()
    try:
        req = urllib_request.Request(
            url,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (LemonFish-Research/1.0; +https://github.com/Lvigentini/LemonFish)'
                ),
                'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            },
        )
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'html' not in content_type.lower() and 'text' not in content_type.lower():
                return None
            raw = resp.read(max_chars * 8)  # over-read; HTML inflates
        text = _strip_html(raw.decode('utf-8', errors='replace'))
        return text[:max_chars]
    except urllib_error.URLError as e:
        logger.debug(f"fetch failed url={url} reason={e.reason}")
        return None
    except Exception as e:
        logger.debug(f"fetch failed url={url} {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class ApiRunner(CLIRunner):
    """LLM + web-search runner. Always available if an LLM API key is set."""

    name = 'api'

    def __init__(self) -> None:
        self._llm_client = None  # lazy

    def _get_llm_client(self):
        """Lazily build an LLMClient for the research_plan step."""
        if self._llm_client is not None:
            return self._llm_client
        LLMClient, Config = _import_llm_client()
        # Use the research_plan step config; if unset, falls back to primary LLM_*.
        # The plan/synthesis split is handled in the orchestrator — runners
        # just use whichever model the plan step is configured to use, since
        # per-sub-topic summarisation is similar in nature to planning.
        cfg = Config.get_step_llm_config('research_plan')
        self._llm_client = LLMClient(**cfg)
        return self._llm_client

    # -- availability --------------------------------------------------------

    def is_available(self) -> AvailabilityResult:
        # Two requirements: (1) DDG package importable, (2) LLM API key set.
        try:
            search_ddg._import_ddgs()
        except search_ddg.SearchUnavailable as e:
            return AvailabilityResult(
                name=self.name,
                available=False,
                reason=str(e),
            )

        try:
            from app.config import Config
        except ImportError as e:
            return AvailabilityResult(
                name=self.name,
                available=False,
                reason=f"app.config not importable: {e}",
            )

        cfg = Config.get_step_llm_config('research_plan')
        if not cfg.get('api_key'):
            return AvailabilityResult(
                name=self.name,
                available=True,
                auth_ok=False,
                reason='LLM_API_KEY (or LLM_RESEARCH_PLAN_API_KEY) not set',
            )
        return AvailabilityResult(
            name=self.name,
            available=True,
            auth_ok=True,
            version='api-runner-1',
        )

    # -- run -----------------------------------------------------------------

    def run(self, sub_topic: SubTopic, system_prompt: str, timeout: int) -> ResearchSummary:
        deadline = time.monotonic() + timeout

        def _check_deadline():
            if time.monotonic() > deadline:
                raise ResearchTimeoutError(
                    f"ApiRunner timed out for sub-topic {sub_topic.index} ({sub_topic.topic!r})"
                )

        # 1. Search ----------------------------------------------------------
        query = self._build_query(sub_topic)
        results = search_ddg.search(
            query,
            max_results=research_config.API_RUNNER_SEARCH_RESULTS,
        )
        if not results:
            logger.warning(f"ApiRunner: no DDG results for {query!r}")

        _check_deadline()

        # 2. Fetch top N -----------------------------------------------------
        sources: List[Tuple[str, str, str]] = []  # (url, title, text)
        fetch_top = research_config.API_RUNNER_FETCH_TOP
        for r in results[:fetch_top]:
            text = _fetch_url(r.url, timeout=min(15, max(5, int(deadline - time.monotonic()))))
            if text:
                sources.append((r.url, r.title, text))
            _check_deadline()

        # If no fetches succeeded, fall back to using snippets only — better
        # than failing the whole sub-topic.
        if not sources:
            for r in results[:fetch_top]:
                if r.snippet:
                    sources.append((r.url, r.title, r.snippet))

        if not sources:
            raise ResearchRunnerError(
                f"ApiRunner: no usable search results for sub-topic {sub_topic.index} ({sub_topic.topic!r})"
            )

        # 3. Summarise via LLM ----------------------------------------------
        try:
            client = self._get_llm_client()
        except Exception as e:
            raise ResearchAuthError(f"ApiRunner: failed to initialise LLM client: {e}") from e

        user_prompt = self._build_user_prompt(sub_topic, sources)
        try:
            body = client.chat(
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.3,
                max_tokens=2400,
            )
        except Exception as e:
            raise ResearchRunnerError(
                f"ApiRunner: LLM call failed for sub-topic {sub_topic.index}: {type(e).__name__}: {e}"
            ) from e

        # 4. Build summary ---------------------------------------------------
        # Citations: in order of appearance in `sources`. The LLM was asked to
        # cite by [n] which corresponds to the source index, but we surface
        # the URLs themselves — the synthesis step does the de-duplication.
        citations = [url for (url, _title, _text) in sources]
        return ResearchSummary(
            sub_topic_index=sub_topic.index,
            runner=self.name,
            body=body.strip(),
            citations=citations,
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _build_query(sub_topic: SubTopic) -> str:
        # Concatenate title + first question; favour brevity for DDG
        if sub_topic.questions:
            return f"{sub_topic.topic}: {sub_topic.questions[0]}"
        return sub_topic.topic

    @staticmethod
    def _build_user_prompt(sub_topic: SubTopic, sources: List[Tuple[str, str, str]]) -> str:
        questions_block = '\n'.join(f"- {q}" for q in sub_topic.questions) or '- (no specific questions)'
        sources_block_parts = []
        for i, (url, title, text) in enumerate(sources, start=1):
            sources_block_parts.append(
                f"=== SOURCE {i} ===\n"
                f"URL: {url}\n"
                f"TITLE: {title or '(untitled)'}\n"
                f"CONTENT:\n{text[:6000]}\n"
            )
        sources_block = '\n'.join(sources_block_parts)

        return (
            f"Sub-topic: {sub_topic.topic}\n\n"
            f"Research questions:\n{questions_block}\n\n"
            f"You have been given source material below. Read it carefully and produce "
            f"a focused, factual summary (~600-1200 words) that addresses the research "
            f"questions. Cite sources inline as [1], [2], etc. corresponding to SOURCE 1, "
            f"SOURCE 2 below. Be concrete: include numbers, dates, named organisations, "
            f"and direct quotes where relevant. If the sources do not answer a question, "
            f"say so explicitly rather than guessing.\n\n"
            f"{sources_block}\n\n"
            f"Now write the summary."
        )
