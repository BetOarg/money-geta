import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.campaign_registry import create_campaign
from scripts.project_registry import create_project
from scripts.providers.search import SearchConfig, SearchRequestError, SearchEvidence
from scripts.campaign_research import canonical_url, rank_discovery_results, run_campaign_research


def _evidence(query, url, *, published_at=None, provider_score=0.5, title="Search result"):
    return SearchEvidence(
        evidence_id=f"id-{query}-{url}", provider="brave", query=query, title=title,
        url=url, snippet="Evidence snippet", published_at=published_at,
        provider_age=None, provider_score=provider_score,
        retrieved_at="2026-11-21T10:00:00+00:00",
    )


def test_canonical_url_removes_tracking_and_fragment_but_keeps_content_params():
    assert canonical_url("HTTPS://Example.org/path/?page=2&utm_source=feed#top") == "https://example.org/path?page=2"


def test_canonical_url_rejects_credentialed_links():
    with pytest.raises(ValueError):
        canonical_url("https://user:pass@example.org/path")
    with pytest.raises(ValueError):
        canonical_url("https://example.org/path?access_token=secret")


def test_rank_deduplicates_results_and_uses_query_coverage_and_freshness():
    now = datetime(2026, 11, 21, tzinfo=timezone.utc)
    results = [
        _evidence("query one", "https://example.org/post?utm_campaign=a#section", published_at="2026-11-20", provider_score=0.91),
        _evidence("query two", "https://example.org/post?utm_campaign=b", published_at="2026-11-20", provider_score=0.7),
        _evidence("query one", "https://other.test/story", published_at="2026-10-01", provider_score=0.1),
    ]
    ranked = rank_discovery_results(results, now=now)
    assert len(ranked) == 2
    top = ranked[0]
    assert top["canonical_url"] == "https://example.org/post"
    assert top["query_count"] == 2
    assert top["source_domain_count"] == 1
    assert top["provider_score"] == 0.91
    assert top["freshest_age_days"] == 1.0
    assert top["discovery_score"] > ranked[1]["discovery_score"]
    assert top["rank"] == 1


def test_rank_ignores_invalid_and_credentialed_urls():
    ranked = rank_discovery_results([
        {"title": "Bad URL", "url": "javascript:alert(1)", "query": "q"},
        {"title": "Creds", "url": "https://user:pass@example.org/", "query": "q"},
    ])
    assert ranked == []


def test_campaign_research_persists_leads_separate_from_claims(monkeypatch, tmp_path):
    import scripts.campaign_research as research

    project_root = tmp_path / "projects"
    create_project("News project", "news", root=project_root)
    create_campaign("news-project", "Daily", "YouTube Shorts", root=project_root)
    calls = []
    def fake_search(query, config):
        calls.append(query)
        return [_evidence(query, "https://example.org/article", published_at="2026-11-21", title=f"Result for {query}")]
    monkeypatch.setattr(research, "search_web", fake_search)
    config = SearchConfig(provider="brave", api_key="dummy", allow_requests=True)
    report = run_campaign_research("news-project", "daily", ["breaking topic", "breaking topic", "official source"], root=project_root, config=config)
    path = Path(report["report_path"])
    assert path.is_file()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert report["status"] == "completed"
    assert report["unique_source_count"] == 1
    assert report["ranked_results"][0]["query_count"] == 2
    assert calls == ["breaking topic", "official source"]
    campaign_dir = path.parent.parent
    assert not (campaign_dir / "source_ledger.jsonl").exists()
    assert not (campaign_dir / "claim_ledger.jsonl").exists()
    assert saved["report_path"] == str(path)


def test_campaign_research_keeps_partial_provider_errors(monkeypatch, tmp_path):
    import scripts.campaign_research as research

    project_root = tmp_path / "projects"
    create_project("Viral", "viral", root=project_root)
    create_campaign("viral", "Campaign", "TikTok", root=project_root)
    def fake_search(query, config):
        if query == "failed query":
            raise SearchRequestError("provider timeout")
        return [_evidence(query, "https://news.example/item", published_at=None)]
    monkeypatch.setattr(research, "search_web", fake_search)
    config = SearchConfig(provider="tavily", api_key="dummy", allow_requests=True)
    report = run_campaign_research("viral", "campaign", ["ok query", "failed query"], root=project_root, config=config)
    assert report["status"] == "partial"
    assert len(report["provider_errors"]) == 1
    assert report["provider_errors"][0]["query"] == "failed query"


def test_campaign_research_limits_queries(monkeypatch, tmp_path):
    import scripts.campaign_research as research
    project_root = tmp_path / "projects"
    create_project("Education", "education", root=project_root)
    create_campaign("education", "Campaign", "YouTube Shorts", root=project_root)
    config = SearchConfig(provider="brave", api_key="dummy", allow_requests=True)
    with pytest.raises(ValueError, match="1 to 10"):
        run_campaign_research("education", "campaign", [f"query {i}" for i in range(11)], root=project_root, config=config)
