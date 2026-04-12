"""
DuckDuckGo search wrapper.

Used by the API fallback runner to discover URLs for a sub-topic. The
duckduckgo-search package is an optional dependency — only required when
the api runner is enabled (RESEARCH_RUNNERS includes 'api'). It is imported
lazily so that simply enabling the research module without 'api' in the
runner list does not require the package to be installed.

Both `ddgs` (the rebrand) and `duckduckgo_search` (the legacy package name)
expose the same `DDGS()` class — we try the new name first.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def to_dict(self) -> dict:
        return {'title': self.title, 'url': self.url, 'snippet': self.snippet}


class SearchUnavailable(RuntimeError):
    """Raised when the DDG search package is not installed."""


def _import_ddgs():
    """Lazily import the DDG client. Tries the new and legacy package names."""
    try:
        from ddgs import DDGS  # type: ignore
        return DDGS
    except ImportError:
        pass
    try:
        from duckduckgo_search import DDGS  # type: ignore
        return DDGS
    except ImportError as e:
        raise SearchUnavailable(
            "DuckDuckGo search package not installed. "
            "Install with: pip install ddgs (or duckduckgo-search)"
        ) from e


def search(query: str, max_results: int = 8, region: str = 'wt-wt') -> List[SearchResult]:
    """Run a DDG text search and return up to max_results.

    Args:
        query: search string
        max_results: maximum number of results to return
        region: DDG region code; 'wt-wt' is global

    Returns:
        List of SearchResult; may be empty if no results or on transient
        provider errors. Caller must handle empty results.

    Raises:
        SearchUnavailable: if the DDG package is not installed
    """
    DDGS = _import_ddgs()
    out: List[SearchResult] = []
    try:
        with DDGS() as ddgs:
            for raw in ddgs.text(query, max_results=max_results, region=region):
                # ddgs returns dicts with 'title', 'href' (or 'url'), 'body'
                url = raw.get('href') or raw.get('url') or ''
                if not url:
                    continue
                out.append(SearchResult(
                    title=str(raw.get('title') or '').strip(),
                    url=url.strip(),
                    snippet=str(raw.get('body') or raw.get('snippet') or '').strip(),
                ))
    except Exception as e:
        logger.warning(f"DDG search failed for query={query!r}: {type(e).__name__}: {e}")
        return []
    return out
