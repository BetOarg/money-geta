import json

import pytest

from scripts.campaign_check import check_file
from scripts.money_geta_gui import build_campaign_payload, save_campaign_manifest, session_video_outputs


def test_campaign_payload_requires_matching_rights_evidence_and_attestations():
    with pytest.raises(ValueError, match="at least one source"):
        build_campaign_payload("Campaign", "YouTube Shorts", [], [], [], [], True, True, True)
    with pytest.raises(ValueError, match="one reference"):
        build_campaign_payload("Campaign", "YouTube Shorts", ["source"], [], [], [], True, True, True)
    with pytest.raises(ValueError, match="Confirm"):
        build_campaign_payload("Campaign", "YouTube Shorts", ["source"], ["rights proof"], [], [], False, True, True)
    with pytest.raises(ValueError, match="credits"):
        build_campaign_payload("Campaign", "YouTube Shorts", ["source"], ["rights proof"], [], [], True, True, False)
    with pytest.raises(ValueError, match="No puedes"):
        build_campaign_payload("Campaign", "YouTube Shorts", ["source"], ["rights proof"], [], ["credit"], True, True, True)


def test_campaign_payload_preserves_explicit_evidence_and_credit_records():
    payload = build_campaign_payload(
        " GTA VI Clips ", " YouTube Shorts ", [" https://example.test/video ", ""],
        [" rights evidence reference ", ""], [" Paid partnership "], [" @creator "],
        True, True, False,
    )
    assert payload["campaign_name"] == "GTA VI Clips"
    assert payload["platform"] == "YouTube Shorts"
    assert payload["sources"] == ["https://example.test/video"]
    assert payload["source_evidence"] == [{"source": "https://example.test/video", "reference": "rights evidence reference"}]
    assert payload["rights_ledger"][0]["status"] == "operator_attested"
    assert payload["permissions_confirmed"] is True
    assert payload["credit_records"] == ["@creator"]
    assert payload["credit_attestation"]["no_credits_required"] is False
    assert payload["required_disclosures"] == ["Paid partnership"]
    assert len(payload["project_id"]) <= 80 and len(payload["campaign_id"]) <= 80


def test_campaign_manifest_saved_in_artifact_registry_layout_and_validates(tmp_path):
    payload = build_campaign_payload(
        "Campaign", "YouTube Shorts", ["https://example.test/source"],
        ["License details checked"], [], [], True, True, True,
    )
    manifest = save_campaign_manifest(payload, tmp_path / "campaigns")
    assert manifest.name == "campaign.json"
    assert manifest.parent.name == payload["campaign_id"]
    assert manifest.parents[2].name == payload["project_id"]
    passed, problems = check_file(manifest)
    assert passed, problems
    assert json.loads(manifest.read_text(encoding="utf-8"))["permission_attestation"]["confirmed"] is True


def test_campaign_payload_requires_either_credits_or_explicit_no_credits():
    with pytest.raises(ValueError, match="credits"):
        build_campaign_payload("Campaign", "YouTube Shorts", ["source"], ["rights proof"], [], [], True, True, False)
    payload = build_campaign_payload("Campaign", "YouTube Shorts", ["source"], ["rights proof"], [], [], True, True, True)
    assert payload["credit_records"] == []
    assert payload["credit_attestation"]["no_credits_required"] is True


def test_session_video_outputs_finds_session_and_manifest_outputs(tmp_path):
    session = tmp_path / "session"
    edits = session / "analysis" / "edits"
    edits.mkdir(parents=True)
    clip = edits / "clip_1.mp4"
    clip.write_bytes(b"clip")
    external = tmp_path / "mpt-output.mp4"
    external.write_bytes(b"render")
    (session / "money-geta.json").write_text(json.dumps({
        "output_videos": [str(external)]
    }), encoding="utf-8")
    outputs = session_video_outputs(session)
    assert set(outputs) == {clip.resolve(), external.resolve()}


def test_session_video_outputs_ignores_missing_manifest_artifacts(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    (session / "money-geta.json").write_text(json.dumps({
        "output_videos": [str(tmp_path / "missing.mp4")]
    }), encoding="utf-8")
    assert session_video_outputs(session) == []
