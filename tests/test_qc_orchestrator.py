import hashlib
import json
from pathlib import Path

import pytest

from scripts.qc_orchestrator import evaluate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def video_report(path, target, data):
    data.update(file=str(target.resolve()), sha256=sha(target))
    path.write_text(json.dumps(data), encoding="utf-8")


def subtitle_report(path, target, data):
    data.update(file=str(target.resolve()), sha256=sha(target))
    path.write_text(json.dumps(data), encoding="utf-8")


def fixture(tmp_path):
    video = tmp_path / "render.mp4"
    video.write_bytes(b"video")
    technical = tmp_path / "technical.json"
    perceptual = tmp_path / "perceptual.json"
    video_report(technical, video, {"schema_version": 1, "passed": True, "problems": []})
    video_report(perceptual, video, {"schema_version": 1, "observations": {}})
    return video, technical, perceptual


def test_ready_requires_technical_and_perceptual_reports(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    result = evaluate(video, technical_report=technical, perceptual_report=perceptual)
    assert result["status"] == "READY_FOR_HUMAN_REVIEW"


def test_missing_perceptual_report_blocks_by_default(tmp_path):
    video, technical, _ = fixture(tmp_path)
    result = evaluate(video, technical_report=technical)
    assert result["status"] == "FAILED"
    assert "Perceptual QC report is required but missing" in result["blocking"]


def test_technical_failure_blocks(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    video_report(technical, video, {"schema_version": 1, "passed": False, "problems": ["no audio"]})
    assert evaluate(video, technical_report=technical, perceptual_report=perceptual)["status"] == "FAILED"


def test_perceptual_findings_require_review_not_fail(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    video_report(perceptual, video, {"schema_version": 1, "observations": {"black_segments": [{"duration": 2}]}})
    result = evaluate(video, technical_report=technical, perceptual_report=perceptual)
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["blocking"] == []


def test_required_subtitle_missing_blocks(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    result = evaluate(video, technical_report=technical, perceptual_report=perceptual, subtitle_required=True)
    assert result["status"] == "FAILED"


def test_wrong_video_target_report_rejected(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    other = tmp_path / "other.mp4"
    other.write_bytes(b"other")
    video_report(technical, other, {"schema_version": 1, "passed": True, "problems": []})
    with pytest.raises(ValueError, match="target path mismatch"):
        evaluate(video, technical_report=technical, perceptual_report=perceptual)


def test_stale_video_hash_rejected(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    video.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash does not match"):
        evaluate(video, technical_report=technical, perceptual_report=perceptual)


def test_subtitle_source_hash_is_checked(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    srt = tmp_path / "captions.srt"
    srt.write_text("caption")
    report = tmp_path / "subtitles.json"
    subtitle_report(report, srt, {"schema_version": 1, "passed": True, "cue_count": 1, "problems": []})
    result = evaluate(video, technical_report=technical, perceptual_report=perceptual, subtitle_report=report)
    assert result["status"] == "READY_FOR_HUMAN_REVIEW"
    srt.write_text("modified caption")
    with pytest.raises(ValueError, match="Subtitle QC hash"):
        evaluate(video, technical_report=technical, perceptual_report=perceptual, subtitle_report=report)


def test_malformed_technical_report_fails_closed(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    video_report(technical, video, {"schema_version": 1, "passed": "yes", "problems": []})
    with pytest.raises(ValueError, match="passed field must be boolean"):
        evaluate(video, technical_report=technical, perceptual_report=perceptual)


def test_malformed_technical_problems_fails_closed(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    video_report(technical, video, {"schema_version": 1, "passed": True, "problems": "none"})
    with pytest.raises(ValueError, match="problems must be a list"):
        evaluate(video, technical_report=technical, perceptual_report=perceptual)


def test_malformed_subtitle_report_fails_closed(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    srt = tmp_path / "captions.srt"
    srt.write_text("caption")
    report = tmp_path / "subtitles.json"
    subtitle_report(report, srt, {"schema_version": 1, "passed": 1, "cue_count": 1, "problems": []})
    with pytest.raises(ValueError, match="passed field must be boolean"):
        evaluate(video, technical_report=technical, perceptual_report=perceptual, subtitle_report=report)


def test_malformed_perceptual_observations_fail_closed(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    video_report(perceptual, video, {"schema_version": 1, "observations": []})
    with pytest.raises(ValueError, match="observations must be a JSON object"):
        evaluate(video, technical_report=technical, perceptual_report=perceptual)


def test_qc_report_symlink_is_rejected(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    alias = tmp_path / "technical-link.json"
    try:
        alias.symlink_to(technical)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(ValueError, match="symlink is blocked"):
        evaluate(video, technical_report=alias, perceptual_report=perceptual)


def test_artifact_symlink_is_rejected(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    alias = tmp_path / "video-link.mp4"
    try:
        alias.symlink_to(video)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(ValueError, match="symlink is blocked"):
        evaluate(alias, technical_report=technical, perceptual_report=perceptual)


def test_technical_signal_observations_survive_aggregation_and_require_review(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    video_report(technical, video, {
        "schema_version": 1, "passed": True, "problems": [],
        "observations": {
            "black_segments": [{"start": 1.0, "end": 2.0, "duration": 1.0}],
            "silence_segments": [{"start": 3.0, "end": 4.0, "duration": 1.0}],
        },
    })
    result = evaluate(video, technical_report=technical, perceptual_report=perceptual)
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["blocking"] == []
    assert result["checks"]["technical"]["observations"]["black_segments"]
    assert result["checks"]["technical"]["observations"]["silence_segments"]


def test_malformed_technical_observations_fail_closed(tmp_path):
    video, technical, perceptual = fixture(tmp_path)
    video_report(technical, video, {
        "schema_version": 1, "passed": True, "problems": [], "observations": []
    })
    with pytest.raises(ValueError, match="Technical QC observations must be a JSON object"):
        evaluate(video, technical_report=technical, perceptual_report=perceptual)
