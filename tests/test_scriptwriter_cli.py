import json
from pathlib import Path

from scripts.campaign_registry import create_campaign, update_campaign
from scripts.project_registry import create_project
from scripts.providers.source_reader import SourceDocument, record_source_document
from scripts.money_geta import main


def _setup_cli_script_campaign(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setenv("MONEY_GETA_PROJECTS_DIR", str(root))
    create_project("CLI project", "viral", root=root)
    create_campaign("cli-project", "CLI campaign", "YouTube Shorts", root=root)
    campaign_id = "cli-campaign"
    source_url = "https://example.org/source"
    update_campaign("cli-project", campaign_id, sources=[source_url], rights_evidence=["Reviewed terms"],
                   confirm_permissions=True, confirm_credits=True, no_credits_required=True, root=root)
    doc = SourceDocument(
        schema_version=1, evidence_id="cli-evidence", requested_url=source_url,
        final_url=source_url, status_code=200, content_type="text/html",
        title="CLI source", description="Source", text="Captured facts and context.",
        content_sha256="hash", byte_count=20, redirect_count=0,
        retrieved_at="2026-11-21T00:00:00+00:00",
    )
    record_source_document("cli-project", campaign_id, doc, root=root)
    return root, campaign_id


def test_script_draft_cli_reports_saved_draft_without_real_llm_calls(monkeypatch, tmp_path, capsys):
    import scripts.scriptwriter as writer
    root, campaign_id = _setup_cli_script_campaign(tmp_path, monkeypatch)
    monkeypatch.setenv("MONEY_GETA_LLM_BASE_URL", "https://mock.example/v1")
    monkeypatch.setenv("MONEY_GETA_LLM_MODEL", "mock-model")
    monkeypatch.setenv("MONEY_GETA_LLM_API_KEY", "dummy")
    monkeypatch.setenv("MONEY_GETA_LLM_ALLOW_REQUESTS", "true")
    script = {
        "title": "Draft title", "hook": "A short hook", "narration": "Narration text",
        "scenes": [{"visual": "Show footage.", "narration": "Explain briefly."}],
        "cta": "Follow for more.", "source_ids": ["cli-evidence"],
        "claims": [{"claim_id": None, "text": "Fact note", "evidence_ids": ["cli-evidence"]}],
    }
    monkeypatch.setattr(writer, "chat_completion", lambda *args, **kwargs: {"choices": [{"message": {"content": json.dumps(script)}}]})
    code = main(["script-draft", "--project", "cli-project", "--campaign", campaign_id])
    output = capsys.readouterr().out
    assert code == 0
    assert "SCRIPT: DRAFT" in output
    assert "Draft title" in output
    assert "REPORT:" in output
    draft = next((root / "cli-project" / "campaigns" / campaign_id / "drafts").glob("script-*.json"))
    assert json.loads(draft.read_text(encoding="utf-8"))["approval"]["status"] == "pending"


def test_script_draft_cli_blocks_external_llm_when_opt_in_disabled(monkeypatch, tmp_path, capsys):
    import scripts.scriptwriter as writer
    root, campaign_id = _setup_cli_script_campaign(tmp_path, monkeypatch)
    monkeypatch.setenv("MONEY_GETA_LLM_BASE_URL", "https://mock.example/v1")
    monkeypatch.setenv("MONEY_GETA_LLM_MODEL", "mock-model")
    monkeypatch.setenv("MONEY_GETA_LLM_API_KEY", "dummy")
    monkeypatch.setenv("MONEY_GETA_LLM_ALLOW_REQUESTS", "false")
    monkeypatch.setattr(writer, "chat_completion", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM called")))
    code = main(["script-draft", "--project", "cli-project", "--campaign", campaign_id])
    output = capsys.readouterr().out
    assert code == 2
    assert "LLM requests are disabled" in output
