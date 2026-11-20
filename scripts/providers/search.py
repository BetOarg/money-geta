"""Search adapters that normalize provenance-rich web results.

Search is disabled unless MONEY_GETA_SEARCH_ALLOW_REQUESTS=true.
Results are leads/evidence records, not proof that a claim is true.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class SearchConfigurationError(ValueError):
    """The search provider is missing or configured unsafely."""


class SearchRequestError(RuntimeError):
    """A search provider request failed without exposing credentials."""


@dataclass(frozen=True)
class SearchConfig:
    provider: str
    api_key: str | None = None
    allow_requests: bool = False
    timeout_seconds: float = 30.0
    country: str = "AR"
    language: str = "es"
    max_results: int = 8

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "SearchConfig":
        env = os.environ if environ is None else environ
        return cls(
            provider=env.get("MONEY_GETA_SEARCH_PROVIDER", "").strip().lower(),
            api_key=env.get("MONEY_GETA_SEARCH_API_KEY") or None,
            allow_requests=env.get("MONEY_GETA_SEARCH_ALLOW_REQUESTS", "").lower() == "true",
            timeout_seconds=float(env.get("MONEY_GETA_SEARCH_TIMEOUT", "30")),
            country=env.get("MONEY_GETA_SEARCH_COUNTRY", "AR").upper(),
            language=env.get("MONEY_GETA_SEARCH_LANGUAGE", "es").lower(),
            max_results=int(env.get("MONEY_GETA_SEARCH_MAX_RESULTS", "8")),
        )

    def validate(self) -> None:
        if self.provider not in {"brave", "tavily"}:
            raise SearchConfigurationError("Choose MONEY_GETA_SEARCH_PROVIDER=brave or tavily.")
        if not self.api_key:
            raise SearchConfigurationError("MONEY_GETA_SEARCH_API_KEY is required.")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 120:
            raise SearchConfigurationError("Search timeout must be between 0 and 120 seconds.")
        if not 1 <= self.max_results <= 20:
            raise SearchConfigurationError("Search max results must be between 1 and 20.")
        if len(self.country) != 2 or not self.country.isalpha():
            raise SearchConfigurationError("Search country must be a two-letter code.")
        if not self.language or len(self.language) > 12:
            raise SearchConfigurationError("Search language is invalid.")


@dataclass(frozen=True)
class SearchEvidence:
    evidence_id: str
    provider: str
    query: str
    title: str
    url: str
    snippet: str
    published_at: str | None
    provider_score: float | None
    retrieved_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _valid_source_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    return value


def _normalize_results(
    provider: str, query: str, raw_results: Any
) -> list[SearchEvidence]:
    if not isinstance(raw_results, list):
        raise SearchRequestError("Search provider response has no results list.")
    retrieved_at = datetime.now(timezone.utc).isoformat()
    normalized: list[SearchEvidence] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = _valid_source_url(item.get("url"))
        title = item.get("title")
        if not url or not isinstance(title, str) or not title.strip():
            continue
        snippet = item.get("description") or item.get("content") or ""
        if not isinstance(snippet, str):
            snippet = ""
        published = item.get("page_age") or item.get("published_date")
        if not isinstance(published, str):
            published = None
        score = item.get("score")
        if not isinstance(score, (int, float)):
            score = None
        evidence_id = hashlib.sha256((provider + "\n" + query + "\n" + url).encode()).hexdigest()
        normalized.append(SearchEvidence(
            evidence_id=evidence_id,
            provider=provider,
            query=query,
            title=title.strip(),
            url=url,
            snippet=snippet,
            published_at=published,
            provider_score=float(score) if score is not None else None,
            retrieved_at=retrieved_at,
        ))
    return normalized


def _brave_search(query: str, config: SearchConfig) -> list[SearchEvidence]:
    params = urlencode({
        "q": query,
        "country": config.country,
        "search_lang": config.language,
        "count": config.max_results,
        "safesearch": "moderate",
    })
    request = Request(
        "https://api.search.brave.com/res/v1/web/search?" + params,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": config.api_key or "",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=config.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SearchRequestError(f"Brave Search returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError, OSError):
        raise SearchRequestError("Brave Search request failed or timed out.") from None
    except (UnicodeError, json.JSONDecodeError):
        raise SearchRequestError("Brave Search returned invalid JSON.") from None
    try:
        results = data["web"]["results"]
    except (KeyError, TypeError):
        raise SearchRequestError("Brave Search response is missing web.results.") from None
    return _normalize_results("brave", query, results)


def _tavily_search(query: str, config: SearchConfig) -> list[SearchEvidence]:
    payload = {
        "query": query,
        "max_results": config.max_results,
        "search_depth": "basic",
        "topic": "general",
        "include_answer": False,
        "include_raw_content": False,
    }
    request = Request(
        "https://api.tavily.com/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + (config.api_key or ""),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=config.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SearchRequestError(f"Tavily Search returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError, OSError):
        raise SearchRequestError("Tavily Search request failed or timed out.") from None
    except (UnicodeError, json.JSONDecodeError):
        raise SearchRequestError("Tavily Search returned invalid JSON.") from None
    if not isinstance(data, dict):
        raise SearchRequestError("Tavily Search response must be a JSON object.")
    return _normalize_results("tavily", query, data.get("results"))


def search_web(
    query: str, *, config: SearchConfig | None = None
) -> list[SearchEvidence]:
    """Search the web and return normalized, timestamped source records."""
    cfg = config or SearchConfig.from_env()
    cfg.validate()
    if not cfg.allow_requests:
        raise SearchConfigurationError(
            "Search requests are disabled. Set MONEY_GETA_SEARCH_ALLOW_REQUESTS=true "
            "only after reviewing provider, quota and possible charges."
        )
    clean_query = query.strip()
    if not clean_query or len(clean_query) > 600:
        raise SearchConfigurationError("Search query must contain 1 to 600 characters.")
    if cfg.provider == "brave":
        return _brave_search(clean_query, cfg)
    return _tavily_search(clean_query, cfg)
