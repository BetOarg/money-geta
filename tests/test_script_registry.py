import json
from pathlib import Path

import pytest

from scripts.campaign_registry import create_campaign, update_campaign
from scripts.project_registry import create_project
from scripts.providers.source_reader import SourceDocument, record_source_document
from scripts.script_registry import ScriptReviewError, register_script, approve_script, check_script, list_scripts


def _setup_review(tmp_path):
    root = tmp_path / "projects"
    create_project("Review project", "viral", root=root)
    create_campaign("review-project", "Review campaign", "YouTube Shorts", root=root)
    campaign_id = "review-campaign"
    source_url = "https://example.org/source"
    update_campaign("review-project", campaign_id, sources=[source_url], rights_evidence=["Reviewed terms"],
                   confirm_permissions=True, confirm_credits=True, no_credits_required=True, root=root)
    doc = SourceDocument(
        schema_version=1, evidence_id="review-evidence", requested_url=source_url,
        final_url=source_url, status_code=200, content_type="text/html",
        title="Captured source", description="Source description", text="Source excerpt.",
        content_sha256="hash-source", byte_count=14, redirect_count=0,
        retrieved_at="2026-11-21T00:00:00+00:00",
    )
    record_source_document("review-project", campaign_id, doc, root=root)
    draft_dir = root / "review-project" / "campaigns" / campaign_id / "drafts"
    draft_dir.mkdir()
    draft_path = draft_dir / "draft.json"
    draft = {
        "schema_version": 1, "status": "draft", "project_id": "review-project",
        "campaign_id": campaign_id, "profile_id": "viral", "language": "es-AR",
        "model": "mock", "input_sha256": "input-hash", "source_ids": ["review-evidence"],
        "supported_claim_ids": [], "approval": {"status": "pending", "approved_sha256": None},
        "script": {
            "title": "Title", "hook": "Hook", "narration": "Narration", "cta": "CTA",
            "scenes": [{"visual": "Visual", "narration": "Scene narration"}],
            "source_ids": ["review-evidence"], "claims": [],
        },
    }
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    return root, campaign_id, draft_path


def test_script_register_approve_and_hash_check(tmp_path):
    root, campaign_id, draft = _setup_review(tmp_path)
    registered = register_script("review-project", campaign_id, draft, root=root)
    assert registered["event_type"] == "script_registered"
    assert len(registered["sha256"]) == 64
    assert check_script("review-project", campaign_id, registered["script_id"], registered["sha256"], root=root) == (False, ["script approval is pending or rejected"])
    approved = approve_script("review-project", campaign_id, registered["script_id"], registered["sha256"],
                             reviewer="Operator", decision="approved", notes="Reviewed script and citations.", root=root)
    assert approved["decision"] == "approved"
    assert check_script("review-project", campaign_id, registered["script_id"], registered["sha256"], root=root) == (True, [])
    listed = list_scripts("review-project", campaign_id, root=root)
    assert listed[0]["latest_decision"]["reviewer"] == "Operator"
    assert register_script("review-project", campaign_id, draft, root=root)["script_id"] == registered["script_id"]


def test_rejected_script_does_not_pass_approval_gate(tmp_path):
    root, campaign_id, draft = _setup_review(tmp_path)
    registered = register_script("review-project", campaign_id, draft, root=root)
    approve_script("review-project", campaign_id, registered["script_id"], registered["sha256"],
                   reviewer="Operator", decision="rejected", notes="Needs rewrite.", root=root)
    assert check_script("review-project", campaign_id, registered["script_id"], registered["sha256"], root=root)[0] is False


def test_script_edit_after_registration_invalidates_hash_bound_review(tmp_path):
    root, campaign_id, draft = _setup_review(tmp_path)
    registered = register_script("review-project", campaign_id, draft, root=root)
    approve_script("review-project", campaign_id, registered["script_id"], registered["sha256"],
                   reviewer="Operator", root=root)
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["script"]["narration"] = "Edited after approval."
    draft.write_text(json.dumps(payload), encoding="utf-8")
    passed, problems = check_script("review-project", campaign_id, registered["script_id"], registered["sha256"], root=root)
    assert passed is False
    assert "changed" in problems[0]


def test_register_script_rejects_outside_campaign_drafts(tmp_path):
    root, campaign_id, draft = _setup_review(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text(draft.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ScriptReviewError, match="inside the campaign drafts"):
        register_script("review-project", campaign_id, outside, root=root)
