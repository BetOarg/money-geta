import json
from pathlib import Path

from scripts.campaign_registry import create_campaign, update_campaign
from scripts.project_registry import create_project
from scripts.providers.source_reader import SourceDocument, record_source_document
from scripts.script_registry import register_script


def _setup_cli_review(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setenv("MONEY_GETA_PROJECTS_DIR", str(root))
    create_project("Review CLI", "viral", root=root)
    create_campaign("review-cli", "Campaign", "YouTube Shorts", root=root)
    campaign_id = "campaign"
    source_url = "https://example.org/source"
    update_campaign("review-cli", campaign_id, sources=[source_url], rights_evidence=["Rights checked"],
                   confirm_permissions=True, confirm_credits=True, no_credits_required=True, root=root)
    doc = SourceDocument(
        schema_version=1, evidence_id="review-cli-evidence", requested_url=source_url,
        final_url=source_url, status_code=200, content_type="text/html",
        title="Source", description="", text="Captured text",
        content_sha256="hash", byte_count=12, redirect_count=0,
        retrieved_at="2026-11-21T00:00:00+00:00",
    )
    record_source_document("review-cli", campaign_id, doc, root=root)
    folder = root / "review-cli" / "campaigns" / campaign_id / "drafts"
    folder.mkdir()
    draft = folder / "script.json"
    payload = {
        "schema_version": 1, "status": "draft", "project_id": "review-cli", "campaign_id": campaign_id,
        "profile_id": "viral", "language": "es-AR", "model": "mock", "input_sha256": "hash",
        "source_ids": ["review-cli-evidence"], "supported_claim_ids": [],
        "approval": {"status": "pending", "approved_sha256": None},
        "script": {"title": "CLI title", "hook": "Hook", "narration": "Narration", "cta": "CTA",
            "scenes": [{"visual": "Visual", "narration": "Scene"}],
            "source_ids": ["review-cli-evidence"], "claims": []},
    }
    draft.write_text(json.dumps(payload), encoding="utf-8")
    return root, campaign_id, draft


def test_script_review_cli_register_approve_check(monkeypatch, tmp_path, capsys):
    root, campaign_id, draft = _setup_cli_review(tmp_path, monkeypatch)
    registered = register_script("review-cli", campaign_id, draft, root=root)
    code = main(["script-review", "approve", "--project", "review-cli", "--campaign", campaign_id,
        "--script-id", registered["script_id"], "--sha256", registered["sha256"],
        "--reviewer", "Operator", "--decision", "approved", "--notes", "Reviewed"])
    output = capsys.readouterr().out
    assert code == 0
    assert "approved" in output
    code = main(["script-review", "check", "--project", "review-cli", "--campaign", campaign_id,
        "--script-id", registered["script_id"], "--sha256", registered["sha256"])
    output = capsys.readouterr().out
    assert code == 0
    assert "SCRIPT_APPROVAL: PASS" in output
