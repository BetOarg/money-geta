import json
from pathlib import Path

import pytest

from scripts.campaign_registry import create_campaign, update_campaign
from scripts.project_registry import create_project
from scripts.providers.llm import LLMConfig, ProviderConfigurationError, ProviderRequestError
from scripts.providers.source_reader import SourceDocument, record_source_document
from scripts.scriptwriter import draft_campaign_script, validate_script_payload


def _setup_campaign(tmp_path, *, profile="viral", add_source=True):
    root = tmp_path / "projects"
    create_project("Script project", profile, topic="Sample topic", root=root)
    create_campaign("script-project", "Shorts campaign", "YouTube Shorts", root=root)
    campaign_id = "shorts-campaign"
    source_url = "https://example.org/source"
    if add_source:
        update_campaign("script-project", campaign_id, sources=[source_url], rights_evidence=["Reviewed source terms"],
                       confirm_permissions=True, confirm_credits=True, no_credits_required=True, root=root)
        doc = SourceDocument(
            schema_version=1, evidence_id="evidence-123", requested_url=source_url,
            final_url=source_url, status_code=200, content_type="text/html",
            title="Sample source", description="Description", text="Verified source text. Details and context.",
            content_sha256="sha256-source", byte_count=44, redirect_count=0,
            retrieved_at="2026-11-21T00:00:00+00:00",
        )
        record_source_document("script-project", campaign_id, doc, root=root)
    return root, campaign_id, source_url


def _llm_config(allow=True):
    return LLMConfig(base_url="https://mock.example/v1", model="mock-model", api_key="test-only", allow_requests=allow)


def _mock_response(source_id):
    script = {
        "title": "Sample video title", "hook": "This detail changes the scene",
        "narration": "Based on the captured source, here is the short explanation.",
        "scenes": [{"visual": "Show the relevant scene.", "narration": "Explain the verified detail."}],
        "cta": "Follow for more context.", "source_ids": [source_id],
        "claims": [{"claim_id": None, "text": "The verified detail.", "evidence_ids": [source_id]}],
    }
    return {"choices": [{"message": {"content": json.dumps(script)}}]}


def test_validate_script_requires_source_citations_and_scene_structure():
    valid = {
        "title": "Title", "hook": "Hook", "narration": "Narration",
        "scenes": [{"visual": "Visual", "narration": "Scene narration"}],
        "cta": "CTA", "source_ids": ["source-1"],
        "claims": [{"claim_id": None, "text": "Claim text", "evidence_ids": ["source-1"}],
    }
    assert validate_script_payload(valid, evidence_ids={"source-1"}, supported_claims=[], factual_required=False)
    invalid = dict(valid, source_ids=["not-known"])
    with pytest.raises(ValueError, match="captured evidence"):
        validate_script_payload(invalid, evidence_ids={"source-1"}, supported_claims=[], factual_required=False)


def test_news_script_claim_must_exactly_match_supported_claim_and_evidence():
    supported = [{"claim_id": "claim-1", "claim": "Exact fact", "status": "supported", "evidence_ids": ["source-1", "source-2"]}]
    payload = {
        "title": "Title", "hook": "Hook", "narration": "Narration",
        "scenes": [{"visual": "Visual", "narration": "Scene narration"}], "cta": "CTA",
        "source_ids": ["source-1", "source-2"],
        "claims": [{"claim_id": "claim-1", "text": "Exact fact", "evidence_ids": ["source-1", "source-2"}],
    }
    assert validate_script_payload(payload, evidence_ids={"source-1", "source-2"}, supported_claims=supported, factual_required=True)
    changed = json.loads(json.dumps(payload))
    changed["claims"][0]["text"] = "Fact altered by the model"
    with pytest.raises(ValueError, match="match supported claim text"):
        validate_script_payload(changed, evidence_ids={"source-1", "source-2"}, supported_claims=supported, factual_required=True)


def test_draft_script_uses_captured_source_and_saves_unapproved_artifact(monkeypatch, tmp_path):
    import scripts.scriptwriter as writer
    root, campaign_id, source_url = _setup_campaign(tmp_path)
    called = {}
    monkeypatch.setattr(writer, "chat_completion", lambda messages, **kwargs: (
        called.update({"messages": messages, "kwargs": kwargs}) or _mock_response("evidence-123")
    ))
    report = draft_campaign_script("script-project", campaign_id, root=root, config=_llm_config())
    path = Path(report["report_path"])
    assert path.is_file()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert report["status"] == "draft"
    assert report["approval"]["status"] == "pending"
    assert report["source_ids"] == ["evidence-123"]
    assert "Verified source text" in called["messages"][1]["content"]
    assert called["kwargs"]["max_tokens"] == 2000
    assert saved["script"]["title"] == "Sample video title"


def test_draft_script_blocks_llm_when_opt_in_disabled(monkeypatch, tmp_path):
    import scripts.scriptwriter as writer
    root, campaign_id, _ = _setup_campaign(tmp_path)
    monkeypatch.setattr(writer, "chat_completion", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM called")))
    with pytest.raises(ProviderConfigurationError, match="disabled"):
        draft_campaign_script("script-project", campaign_id, root=root, config=_llm_config(False))


def test_draft_script_requires_captured_source_docs(monkeypatch, tmp_path):
    import scripts.scriptwriter as writer
    root, campaign_id, _ = _setup_campaign(tmp_path, add_source=False)
    monkeypatch.setattr(writer, "chat_completion", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM called")))
    with pytest.raises(ValueError, match="source_ledger"):
        draft_campaign_script("script-project", campaign_id, root=root, config=_llm_config())


def test_draft_script_rejects_non_json_provider_output(monkeypatch, tmp_path):
    import scripts.scriptwriter as writer
    root, campaign_id, _ = _setup_campaign(tmp_path)
    monkeypatch.setattr(writer, "chat_completion", lambda *args, **kwargs: {"choices": [{"message": {"content": "not json"}}]})
    with pytest.raises(ProviderRequestError, match="valid JSON"):
        draft_campaign_script("script-project", campaign_id, root=root, config=_llm_config())


def test_draft_script_rejects_missing_campaign_rights_gate(monkeypatch, tmp_path):
    import scripts.scriptwriter as writer
    root = tmp_path / "projects"
    create_project("No evidence", "viral", root=root)
    create_campaign("no-evidence", "Campaign", "YouTube Shorts", root=root)
    monkeypatch.setattr(writer, "chat_completion", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM called")))
    with pytest.raises(ValueError, match="Campaign gate blocked"):
        draft_campaign_script("no-evidence", "campaign", root=root, config=_llm_config())
