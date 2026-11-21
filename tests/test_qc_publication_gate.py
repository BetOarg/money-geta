import json
from pathlib import Path

import pytest

from scripts.artifact_registry import register_artifact, run_artifact_qc
from tests.test_artifact_registry import setup_campaign


def test_technical_qc_is_recorded_for_exact_artifact_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    import scripts.quality_control as qc
    monkeypatch.setattr(qc, "inspect_media", lambda *a, **k: {
        "passed": True, "problems": [], "probe": {"format": {"duration": "10"}}
    })
    event = run_artifact_qc(campaign, item["artifact_id"], item["sha256"])
    assert event["passed"] is True
    rows = json.loads((campaign.parent / "artifact_ledger.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rows["event_type"] == "artifact_qc"
    assert rows["sha256"] == item["sha256"


def test_failed_latest_qc_is_recorded_and_bound_to_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    import scripts.quality_control as qc
    monkeypatch.setattr(qc, "inspect_media", lambda *a, **k: {
        "passed": False, "problems": ["missing audio"], "probe": {}
    })
    result = run_artifact_qc(campaign, item["artifact_id"], item["sha256"])
    assert result["passed"] is False
    assert "missing audio" in result["problems"


def test_publication_check_requires_technical_qc_event(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    from scripts.artifact_registry import main
    assert main(["--campaign", str(campaign), "publication-check",
                 "--artifact-id", item["artifact_id"], "--sha256", item["sha256"]]) == 2
