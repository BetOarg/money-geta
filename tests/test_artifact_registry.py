import json
from pathlib import Path

import pytest

from scripts.artifact_registry import (
    ArtifactReviewError, approve_artifact, check_artifact, register_artifact,
)


def setup_campaign(tmp_path: Path) -> tuple[Path, Path]:
    folder = tmp_path / "projects" / "project-a" / "campaigns" / "campaign-a"
    folder.mkdir(parents=True)
    campaign = folder / "campaign.json"
    campaign.write_text(json.dumps({
        "schema_version": 1, "project_id": "project-a", "campaign_id": "campaign-a"
    }), encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    return campaign, output


def test_artifact_requires_human_approval_and_exact_hash(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video bytes")
    registered = register_artifact(campaign, video, allowed_root=output, metadata={"engine": "MPT", "format": "9:16"})
    assert len(registered["sha256"]) == 64
    passed, problems = check_artifact(campaign, registered["artifact_id"], registered["sha256"])
    assert not passed
    assert "human approval" in problems[0]
    approve_artifact(campaign, registered["artifact_id"], registered["sha256"], reviewer="operator")
    assert check_artifact(campaign, registered["artifact_id"], registered["sha256"]) == (True, [])


def test_changed_file_invalidates_approval(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"original")
    item = register_artifact(campaign, video, allowed_root=output)
    approve_artifact(campaign, item["artifact_id"], item["sha256"], reviewer="operator")
    video.write_bytes(b"modified")
    passed, problems = check_artifact(campaign, item["artifact_id"], item["sha256"])
    assert not passed
    assert "changed" in problems[0]


def test_wrong_hash_and_unknown_artifact_are_rejected(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    with pytest.raises(ArtifactReviewError, match="does not match"):
        approve_artifact(campaign, item["artifact_id"], "0" * 64, reviewer="operator")
    with pytest.raises(ArtifactReviewError, match="Unknown artifact"):
        approve_artifact(campaign, "a" * 32, "0" * 64, reviewer="operator")


def test_artifact_outside_allowed_root_and_non_mp4_are_rejected(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    video = elsewhere / "final.mp4"
    video.write_bytes(b"video")
    with pytest.raises(ArtifactReviewError, match="allowed output"):
        register_artifact(campaign, video, allowed_root=output)
    text = output / "notes.txt"
    text.write_text("not a video", encoding="utf-8")
    with pytest.raises(ArtifactReviewError, match="allowed output"):
        register_artifact(campaign, text, allowed_root=output)


def test_symlink_artifact_is_rejected_when_supported(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    target = output / "target.mp4"
    target.write_bytes(b"video")
    link = output / "linked.mp4"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(ArtifactReviewError, match="Symlink"):
        register_artifact(campaign, link, allowed_root=output)



def test_latest_rejection_revokes_previous_approval(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    approve_artifact(campaign, item["artifact_id"], item["sha256"], reviewer="operator")
    approve_artifact(campaign, item["artifact_id"], item["sha256"], reviewer="operator",
                     decision="rejected", notes="Logo incorrecto")
    passed, problems = check_artifact(campaign, item["artifact_id"], item["sha256"])
    assert not passed
    assert "latest human decision" in problems[0]


def test_missing_artifact_invalidates_approval(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    approve_artifact(campaign, item["artifact_id"], item["sha256"], reviewer="operator")
    video.unlink()
    passed, problems = check_artifact(campaign, item["artifact_id"], item["sha256"])
    assert not passed
    assert "changed" in problems[0]



def test_nested_artifact_inside_mpt_output_tree_is_allowed(tmp_path: Path) -> None:
    campaign, output = setup_campaign(tmp_path)
    nested = output / "videos" / "vertical"
    nested.mkdir(parents=True)
    video = nested / "final.mp4"
    video.write_bytes(b"nested video")
    item = register_artifact(campaign, video, allowed_root=output)
    assert item["path"] == str(video)
    assert check_artifact(campaign, item["artifact_id"], item["sha256"])[0] is False



def test_central_qc_report_recorded_and_listed(tmp_path: Path) -> None:
    from scripts.artifact_registry import record_central_qc, list_artifacts
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    report = output / "central.json"
    report.write_text(json.dumps({
        "schema_version": 1, "artifact": str(video.resolve()), "sha256": item["sha256"],
        "status": "READY_FOR_HUMAN_REVIEW", "blocking": [], "review": [], "checks": {}
    }), encoding="utf-8")
    event = record_central_qc(campaign, item["artifact_id"], item["sha256"], report)
    assert event["status"] == "READY_FOR_HUMAN_REVIEW"
    listed = list_artifacts(campaign)[0]
    assert listed["latest_central_qc"]["sha256"] == item["sha256"]


def test_central_qc_rejects_report_with_stale_hash(tmp_path: Path) -> None:
    from scripts.artifact_registry import record_central_qc
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    report = output / "central.json"
    report.write_text(json.dumps({
        "schema_version": 1, "artifact": str(video.resolve()), "sha256": "0" * 64,
        "status": "READY_FOR_HUMAN_REVIEW"
    }), encoding="utf-8")
    with pytest.raises(ArtifactReviewError, match="hash does not match"):
        record_central_qc(campaign, item["artifact_id"], item["sha256"], report)


def test_publication_check_blocks_without_central_qc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from scripts.artifact_registry import main, run_artifact_qc
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    import scripts.quality_control as qc
    monkeypatch.setattr(qc, "inspect_media", lambda *a, **k: {
        "passed": True, "problems": [], "probe": {}
    })
    run_artifact_qc(campaign, item["artifact_id"], item["sha256"])
    approve_artifact(campaign, item["artifact_id"], item["sha256"], reviewer="test reviewer")
    import scripts.campaign_check as campaign_check
    monkeypatch.setattr(campaign_check, "check_file", lambda *a, **k: (True, []))
    result = main(["--campaign", str(campaign), "publication-check",
        "--artifact-id", item["artifact_id"], "--sha256", item["sha256"]])
    assert result == 2
    assert "central QC has not been recorded" in capsys.readouterr().out


def test_central_qc_ready_status_rejects_findings(tmp_path: Path) -> None:
    from scripts.artifact_registry import record_central_qc
    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    report = output / "central.json"
    report.write_text(json.dumps({
        "schema_version": 1, "artifact": str(video.resolve()), "sha256": item["sha256"],
        "status": "READY_FOR_HUMAN_REVIEW", "blocking": [], "review": ["Freeze observation"], "checks": {}
    }), encoding="utf-8")
    with pytest.raises(ArtifactReviewError, match="cannot contain blocking issues or review findings"):
        record_central_qc(campaign, item["artifact_id"], item["sha256"], report)


def test_review_required_central_qc_needs_acknowledgement_and_new_artifact_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from scripts.artifact_registry import acknowledge_central_qc, main, record_central_qc, run_artifact_qc
    import scripts.campaign_check as campaign_check
    import scripts.quality_control as qc

    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    monkeypatch.setattr(qc, "inspect_media", lambda *a, **k: {"passed": True, "problems": [], "probe": {}})
    run_artifact_qc(campaign, item["artifact_id"], item["sha256"])
    report = output / "central.json"
    report.write_text(json.dumps({
        "schema_version": 1, "artifact": str(video.resolve()), "sha256": item["sha256"],
        "status": "REVIEW_REQUIRED", "blocking": [],
        "review": ["Black segment detected; inspect the actual footage."], "checks": {},
    }), encoding="utf-8")
    record_central_qc(campaign, item["artifact_id"], item["sha256"], report)
    approve_artifact(campaign, item["artifact_id"], item["sha256"], reviewer="operator")
    monkeypatch.setattr(campaign_check, "check_file", lambda *a, **k: (True, []))
    args = ["--campaign", str(campaign), "publication-check",
            "--artifact-id", item["artifact_id"], "--sha256", item["sha256"]]
    assert main(args) == 2
    assert "explicit human acknowledgement" in capsys.readouterr().out

    acknowledged = acknowledge_central_qc(
        campaign, item["artifact_id"], item["sha256"],
        reviewer="operator", notes="Reviewed the black segment; it is an intentional fade.",
    )
    assert acknowledged["event_type"] == "artifact_central_qc_reviewed"
    # The final artifact approval must occur after the acknowledgement.
    approve_artifact(campaign, item["artifact_id"], item["sha256"], reviewer="operator",
                     notes="Approved after QC findings review.")
    assert main(args) == 0
    assert "READY_FOR_HUMAN_PUBLISH_ACTION" in capsys.readouterr().out


def test_central_qc_acknowledgement_rejects_ready_or_failed_status(tmp_path: Path) -> None:
    from scripts.artifact_registry import acknowledge_central_qc, record_central_qc

    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    report = output / "central.json"
    report.write_text(json.dumps({
        "schema_version": 1, "artifact": str(video.resolve()), "sha256": item["sha256"],
        "status": "READY_FOR_HUMAN_REVIEW", "blocking": [], "review": [], "checks": {},
    }), encoding="utf-8")
    record_central_qc(campaign, item["artifact_id"], item["sha256"], report)
    with pytest.raises(ArtifactReviewError, match="Only REVIEW_REQUIRED"):
        acknowledge_central_qc(campaign, item["artifact_id"], item["sha256"], reviewer="operator")


def test_central_qc_acknowledgement_requires_reviewer(tmp_path: Path) -> None:
    from scripts.artifact_registry import acknowledge_central_qc, record_central_qc

    campaign, output = setup_campaign(tmp_path)
    video = output / "final.mp4"
    video.write_bytes(b"video")
    item = register_artifact(campaign, video, allowed_root=output)
    report = output / "central.json"
    report.write_text(json.dumps({
        "schema_version": 1, "artifact": str(video.resolve()), "sha256": item["sha256"],
        "status": "REVIEW_REQUIRED", "blocking": [], "review": ["Observation"], "checks": {},
    }), encoding="utf-8")
    record_central_qc(campaign, item["artifact_id"], item["sha256"], report)
    with pytest.raises(ArtifactReviewError, match="reviewer is required"):
        acknowledge_central_qc(campaign, item["artifact_id"], item["sha256"], reviewer=" ")
