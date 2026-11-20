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
