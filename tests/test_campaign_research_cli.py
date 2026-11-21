import json
from pathlib import Path

from scripts.campaign_registry import create_campaign
from scripts.project_registry import create_project
from scripts.providers.search import SearchConfig, SearchEvidence
from scripts.money_geta import main


def _mock_evidence(query, url):
    return SearchEvidence(
        evidence_id="evidence-" + query, provider="brave", query=query, title="Mock source",
        url=url, snippet="Mocked source result", published_at="2026-11-21",
        provider_age=None, provider_score=0.8, retrieved_at="2026-11-21T00:00:00+00:00",
    )


def _setup_project(tmp_path, monkeypatch, project="Research project", campaign="Campaign"):
    root = tmp_path / "projects"
    monkeypatch.setenv("MONEY_GETA_PROJECTS_DIR", str(root))
    project_id = project.lower().replace(" ", "-")
    campaign_id = campaign.lower().replace(" ", "-")
    create_project(project, "viral", root=root)
    create_campaign(project_id, campaign, "YouTube Shorts", root=root)
    return root, project_id, campaign_id


def test_cli_research_saves_ranked_report_without_network(monkeypatch, tmp_path, capsys):
    import scripts.campaign_research as research
    root, project_id, campaign_id = _setup_project(tmp_path, monkeypatch)
    monkeypatch.setenv("MONEY_GETA_SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("MONEY_GETA_SEARCH_API_KEY", "test-only-key")
    monkeypatch.setenv("MONEY_GETA_SEARCH_ALLOW_REQUESTS", "true")
    queries = []
    monkeypatch.setattr(research, "search_web", lambda query, config: (
        queries.append(query) or [_mock_evidence(query, "https://example.org/story")]
    ))
    code = main(["research", "--project", project_id, "--campaign", campaign_id,
                 "--query", "topic today", "--query", "topic today", "--query", "official context"])
    output = capsys.readouterr().out
    assert code == 0
    assert "RESEARCH: COMPLETED" in output
    assert "REPORT:" in output
    assert queries == ["topic today", "official context"]
    report_path = next((root / project_id / "campaigns" / campaign_id / "research").glob("discovery-*.json"))
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["unique_source_count"] == 1
    assert saved["ranked_results"][0]["query_count"] == 2


def test_cli_research_requires_explicit_provider_opt_in(monkeypatch, tmp_path, capsys):
    import scripts.campaign_research as research
    root, project_id, campaign_id = _setup_project(tmp_path, monkeypatch, "Opt-in", "Test")
    monkeypatch.setenv("MONEY_GETA_SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("MONEY_GETA_SEARCH_API_KEY", "test-only-key")
    monkeypatch.setenv("MONEY_GETA_SEARCH_ALLOW_REQUESTS", "false")
    monkeypatch.setattr(research, "search_web", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network adapter called")))
    code = main(["research", "--project", project_id, "--campaign", campaign_id, "--query", "topic"])
    output = capsys.readouterr().out
    assert code == 2
    assert "requests are disabled" in output
