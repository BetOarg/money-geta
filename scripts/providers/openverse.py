"""Openverse image discovery adapter; candidates remain unverified until human review."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import Request, urlopen

from scripts.campaign_registry import get_campaign
from scripts.project_registry import default_projects_root, get_project
from scripts.providers.source_reader import SECRET_QUERY


class ImageSearchConfigurationError(ValueError):
    """Image search settings are invalid or requests are not explicitly enabled."""


class ImageSearchRequestError(RuntimeError):
    """Image provider request failed without leaking credentials."""


@dataclass(frozen=True)
class ImageSearchConfig:
    allow_requests: bool = False
    timeout_seconds: float = 20.0
    max_results: int = 12
    endpoint: str = "https://api.openverse.org/v1/images/"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ImageSearchConfig":
        env = os.environ if environ is None else environ
        return cls(
            allow_requests=env.get("MONEY_GETA_IMAGE_SEARCH_ALLOW_REQUESTS", "").lower() == "true",
            timeout_seconds=float(env.get("MONEY_GETA_IMAGE_SEARCH_TIMEOUT", "20")),
            max_results=int(env.get("MONEY_GETA_IMAGE_SEARCH_MAX_RESULTS", "12")),
        )

    def validate(self) -> None:
        parsed = urlsplit(self.endpoint)
        if parsed.scheme != "https" or parsed.hostname != "api.openverse.org" or parsed.path.rstrip("/") != "/v1/images":
            raise ImageSearchConfigurationError("Image discovery only permits the official HTTPS Openverse API endpoint.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ImageSearchConfigurationError("Openverse endpoint must not include credentials or query parameters.")
        if not 1 <= self.max_results <= 20:
            raise ImageSearchConfigurationError("Image search result limit must be 1–20.")
        if not 1 <= self.timeout_seconds <= 60:
            raise ImageSearchConfigurationError("Image search timeout must be 1–60 seconds.")


@dataclass(frozen=True)
class ImageCandidate:
    candidate_id: str
    provider: str
    query: str
    title: str
    image_url: str
    source_page_url: str
    creator: str
    creator_url: str | None
    license: str
    license_version: str | None
    license_url: str | None
    provider_source: str | None
    category: str | None
    thumbnail_url: str | None
    width: int | None
    height: int | None
    attribution: str
    retrieved_at: str
    rights_status: str = "unverified"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


METADATA_FIELDS = (
    "candidate_id", "provider", "title", "image_url", "source_page_url",
    "creator", "creator_url", "license", "license_version", "license_url",
    "provider_source", "category", "thumbnail_url", "width", "height", "attribution",
)


def candidate_metadata_hash(candidate: dict[str, Any]) -> str:
    stable = {key: candidate.get(key) for key in METADATA_FIELDS}
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _valid_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    if any(SECRET_QUERY.search(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        return None
    return value


def _normalize(query: str, results: Any) -> list[ImageCandidate]:
    if not isinstance(results, list):
        raise ImageSearchRequestError("Openverse response has no results list.")
    now = datetime.now(timezone.utc).isoformat()
    normalized = []
    for item in results:
        if not isinstance(item, dict):
            continue
        image_url = _valid_url(item.get("url"))
        source_page = _valid_url(item.get("foreign_landing_url"))
        title = item.get("title")
        license = item.get("license")
        if not image_url or not source_page or not isinstance(title, str) or not title.strip() or not isinstance(license, str) or not license.strip():
            continue
        creator = item.get("creator") if isinstance(item.get("creator"), str) else ""
        creator_url = _valid_url(item.get("creator_url"))
        license_url = _valid_url(item.get("license_url"))
        thumbnail = _valid_url(item.get("thumbnail"))
        license_version = item.get("license_version") if isinstance(item.get("license_version"), str) else None
        provider_source = item.get("source") if isinstance(item.get("source"), str) else None
        category = item.get("category") if isinstance(item.get("category"), str) else None
        width = item.get("width") if isinstance(item.get("width"), int) and item["width"] > 0 else None
        height = item.get("height") if isinstance(item.get("height"), int) and item["height"] > 0 else None
        attribution = item.get("attribution") if isinstance(item.get("attribution"), str) else ""
        candidate_id = hashlib.sha256((image_url + "\n" + source_page).encode("utf-8")).hexdigest()
        normalized.append(ImageCandidate(
            candidate_id=candidate_id, provider="openverse", query=query.strip(),
            title=title.strip()[:500], image_url=image_url, source_page_url=source_page,
            creator=creator[:300], creator_url=creator_url, license=license.strip().lower(),
            license_version=license_version, license_url=license_url, provider_source=provider_source,
            category=category, thumbnail_url=thumbnail, width=width, height=height,
            attribution=attribution[:1000], retrieved_at=now,
        ))
    return normalized


def search_openverse(query: str, *, config: ImageSearchConfig | None = None, aspect_ratio: str = "tall") -> list[ImageCandidate]:
    if not isinstance(query, str) or not query.strip() or len(query.strip()) > 200:
        raise ValueError("Image search query must contain 1–200 characters.")
    if aspect_ratio not in {"tall", "wide", "square"}:
        raise ValueError("Aspect ratio must be tall, wide or square.")
    cfg = config or ImageSearchConfig.from_env()
    cfg.validate()
    if not cfg.allow_requests:
        raise ImageSearchConfigurationError("Image search requests are disabled. Review rate limits and usage before enabling MONEY_GETA_IMAGE_SEARCH_ALLOW_REQUESTS=true.")
    params = urlencode({"q": query.strip(), "page_size": cfg.max_results, "license_type": "commercial", "aspect_ratio": aspect_ratio, "mature": "false", "filter_dead": "true"})
    request = Request(cfg.endpoint + "?" + params, headers={"Accept": "application/json", "User-Agent": "Money-Geta/0.1"}, method="GET")
    try:
        with urlopen(request, timeout=cfg.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ImageSearchRequestError(f"Openverse returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError, OSError):
        raise ImageSearchRequestError("Openverse request failed or timed out.") from None
    except (UnicodeError, json.JSONDecodeError):
        raise ImageSearchRequestError("Openverse returned invalid JSON.") from None
    try:
        return _normalize(query, data["results"])
    except (KeyError, TypeError):
        raise ImageSearchRequestError("Openverse response structure is incomplete.") from None


def save_image_candidates(project_id: str, campaign_id: str, candidates: list[ImageCandidate], *, root: Path | None = None) -> dict[str, Any]:
    projects_root = (root or default_projects_root()).expanduser().resolve()
    get_project(project_id, projects_root)
    get_campaign(project_id, campaign_id, projects_root)
    campaign_file = projects_root / project_id / "campaigns" / campaign_id / "campaign.json"
    from scripts.artifact_registry import _reject_symlink_components
    _reject_symlink_components(campaign_file)
    resolved = campaign_file.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(projects_root):
        raise ValueError("Campaign manifest must be a regular file inside projects root.")
    ledger = resolved.parent / "media_candidates.jsonl"
    _reject_symlink_components(ledger)
    existing_hashes: dict[str, str] = {}
    if ledger.exists():
        if not ledger.is_file():
            raise ValueError("Media candidate ledger is not a regular file.")
        try:
            for line in ledger.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(event.get("candidate_id"), str):
                    raise ValueError("Media candidate ledger contains malformed records.")
                existing_hashes[event["candidate_id"]] = candidate_metadata_hash(event)
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ValueError("Media candidate ledger is malformed or unreadable.") from None
    ledger.resolve(strict=False)
    appended = 0
    with ledger.open("a", encoding="utf-8", newline="\\n") as handle:
        for candidate in candidates:
            record = candidate.to_dict()
            metadata_hash = candidate_metadata_hash(record)
            if existing_hashes.get(record["candidate_id"]) == metadata_hash:
                continue
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\\n")
            existing_hashes[record["candidate_id"]] = metadata_hash
            appended += 1
        handle.flush()
        os.fsync(handle.fileno())
    return {"path": str(ledger), "added": appended, "total": len(existing_hashes)}
