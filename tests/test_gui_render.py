import json

import pytest

from scripts.money_geta_gui import build_campaign_payload, session_video_outputs


def test_campaign_payload_requires_rights_credits_and_sources():
    with pytest.raises(ValueError):
        build_campaign_payload("Campaign", "YouTube Shorts", [], [], True, True)
    with pytest.raises(ValueError):
        build_campaign_payload("Campaign", "YouTube Shorts", ["source"], [], False, True)
    with pytest.raises(ValueError):
        build_campaign_payload("Campaign", "YouTube Shorts", ["source"], [], True, False)


def test_campaign_payload_preserves_explicit_evidence():
    payload = build_campaign_payload(
        " GTA VI Clips ", " YouTube Shorts ", [" https://example.test/video ", ""],
        [" Paid partnership "], True, True,
    )
    assert payload == {
        "campaign_name": "GTA VI Clips",
        "platform": "YouTube Shorts",
        "permissions_confirmed": True,
        "credits_confirmed": True,
        "sources": ["https://example.test/video"],
        "required_disclosures": ["Paid partnership"],
    }


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
