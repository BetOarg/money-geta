"""Campaign research discovery with deduplication and transparent relevance signals."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from scripts.campaign_registry import get_campaign
from scripts.project_registry import default_projects_root, get_project
from scripts.providers.search import SearchConfig, SearchRequestError, search_web

TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
TRACKING_PREFIXES = ("utm_",)


def canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Research source URL must be HTTP(S) without embedded credentials.")
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    if any(re.search(r"(?:token|api[_-]?key|access[_-]?token|auth|signature|secret|password|credential)", key, re.I) for key, _ in query_items):
        raise ValueError("Credential-like URL parameters are blocked from research reports.")
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    port = parsed.port
    if port and port != (443 if parsed.scheme.lower() == "https" else 80):
        host = f"{host}:{port}"
    query = sorted((key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
                   if key.lower() not in TRACKING_KEYS and not key.lower().startswith(TRACKING_PREFIXES))
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), host, path, urlencode(query), ""))


def _publication_age(published_at: str | None, now: datetime) -> float | None:
    if not published_at:
        return None
    try:
        value = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0.0, (now - value.astimezone(timezone.utc)).total_seconds() / 86400)


def rank_discovery_results(results: list[Any], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Rank results by query coverage, bounded provider score and explicit freshness."""
    current = now or datetime.now(timezone.utc)
    grouped: dict[str, dict[str, Any]] = {}
    for evidence in results:
        data = evidence.to_dict() if hasattr(evidence, "to_dict") else dict(evidence)
        url = data.get("url")
        title = data.get("title")
        if not isinstance(url, str) or not isinstance(title, str) or not title.strip():
            continue
        try:
            key = canonical_url(url)
        except ValueError:
            continue
        record = grouped.setdefault(key, {
            "canonical_url": key, "title": title.strip(), "snippet": data.get("snippet", ""),
            "query_hits": [], "domains": set(), "provider_scores": [], "published_dates": [],
            "evidence": [],
        })
        query = data.get("query")
        if isinstance(query, str) and query.strip() and query.strip() not in record["query_hits"]:
            record["query_hits"].append(query.strip())
        host = urlsplit(key).hostname
        if host:
            record["domains"].add(host)
        score = data.get("provider_score")
        if isinstance(score, (int, float)):
            record["provider_scores"].append(float(score))
        published = data.get("published_at")
        if isinstance(published, str) and published:
            age = _publication_age(published, current)
            record["published_dates"].append({"published_at": published, "age_days": age})
        record["evidence"].append(data)

    ranked = []
    for record in grouped.values():
        domains = sorted(record.pop("domains"))
        scores = record.pop("provider_scores")
        dates = record.pop("published_dates")
        query_hits = record["query_hits"]
        best_age = min((item["age_days"] for item in dates if item["age_days"] is not None), default=None)
        freshness = max(0.0, 2.0 - best_age / 30.0) if best_age is not None and best_age <= 60 else 0.0
        provider_score = min(1.0, max(0.0, max(scores, default=0.0)))
        score = round(len(query_hits) * 2.0 + provider_score + freshness, 3)
        record.update({
            "query_count": len(query_hits), "source_domain_count": len(domains),
            "source_domains": domains, "provider_score": round(provider_score, 3),
            "published_dates": dates, "freshest_age_days": best_age,
            "freshness_bonus": round(freshness, 3), "discovery_score": score,
        })
        ranked.append(record)
    ranked.sort(key=lambda item: (-item["discovery_score"], item["canonical_url"]))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def run_campaign_research(project_id: str, campaign_id: str, queries: list[str], *,
                        root: Path | None = None, config: SearchConfig | None = None) -> dict[str, Any]:
    """Search opted-in providers, save ranked leads, and keep leads separate from claims/source rights."""
    if not isinstance(queries, list) or not queries:
        raise ValueError("Provide at least one research query.")
    cleaned = list(dict.fromkeys(query.strip() for query in queries if isinstance(query, str) and query.strip()))
    if not cleaned or len(cleaned) > 10 or any(len(query) > 600 for query in cleaned):
        raise ValueError("Research accepts 1 to 10 unique queries, each up to 600 characters.")
    projects_root = (root or default_projects_root()).expanduser().resolve()
    get_project(project_id, projects_root)
    campaign = get_campaign(project_id, campaign_id, projects_root)
    campaign_path = projects_root / project_id / "campaigns" / campaign_id / "campaign.json"
    cfg = config or SearchConfig.from_env()
    cfg.validate()
    if not cfg.allow_requests:
        from scripts.providers.search import SearchConfigurationError
        raise SearchConfigurationError("Search requests are disabled. Set MONEY_GETA_SEARCH_ALLOW_REQUESTS=true only after reviewing provider, quota and possible charges.")
    evidence = []
    errors = []
    for query in cleaned:
        try:
            evidence.extend(item.to_dict() for item in search_web(query, config=cfg))
        except SearchRequestError as exc:
            errors.append({"query": query, "error": str(exc)})
    ranked = rank_discovery_results(evidence)
    status = "failed" if not ranked else ("partial" if errors else "completed")
    report = {
        "schema_version": 1, "research_type": "web_discovery",
        "project_id": project_id, "campaign_id": campaign_id,
        "campaign_name": campaign.get("campaign_name", ""), "profile_id": campaign.get("profile_id", ""),
        "provider": cfg.provider, "queries": cleaned, "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "status": status, "result_count": len(evidence), "unique_source_count": len(ranked),
        "provider_errors": errors, "ranked_results": ranked,
        "limits": {"max_queries": 10, "provider_results_per_query": cfg.max_results},
        "interpretation": "Discovery score reflects query coverage, bounded provider score and explicit publication freshness. It is not a popularity metric or truth/rights verification.",
    }
    from scripts.artifact_registry import _reject_symlink_components
    _reject_symlink_components(campaign_path)
    campaign_file = campaign_path.resolve(strict=True)
    if not campaign_file.is_file() or not campaign_file.is_relative_to(projects_root):
        raise ValueError("Campaign manifest must be a regular file inside the projects root.")
    output_dir = campaign_file.parent / "research"
    _reject_symlink_components(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.is_symlink():
        raise ValueError("Research output directory symlinks are blocked.")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = output_dir / f"discovery-{timestamp}-{uuid.uuid4().hex[:8]}.json"
    report["report_path"] = str(target)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report
