from pathlib import Path

import pytest

from scripts.timeline_preview_qc import review_preview


def test_preview_qc_technical_pass_and_observations(tmp_path):
    media = tmp_path / "preview.mp4"
    media.write_bytes(b"fake-preview")
    timeline = {"plan_type": "editable_timeline", "scenes": [{"duration_seconds": 5}, {"duration_seconds": 4}], "audio_tracks": []}
    report_path = tmp_path / "preview-qc.json"
    def technical(path, **kwargs):
        assert path == media.resolve()
        assert kwargs == {"min_duration": 8.0, "max_duration": 10.0, "expected_aspect": "9:16", "require_audio": False}
        return {"passed": True, "problems": [], "sha256": "x"}
    def perceptual(path, **kwargs):
        return {"observations": {"black_segments": [], "freeze_segments": [], "silence_segments": []}}
    result = review_preview(media, timeline, report_path=report_path, technical_checker=technical, perceptual_checker=perceptual)
    assert result["status"] == "PASS"
    assert result["report_path"] == str(report_path.resolve())
    assert report_path.is_file()


def test_preview_qc_review_required_and_perceptual_error_is_nonblocking(tmp_path):
    media = tmp_path / "preview.mp4"
    media.write_bytes(b"fake")
    timeline = {"plan_type": "editable_timeline", "scenes": [{"duration_seconds": 2}], "audio_tracks": [{"source_path": "x"}]}
    result = review_preview(media, timeline,
        technical_checker=lambda path, **kwargs: {"passed": False, "problems": ["wrong aspect"]},
        perceptual_checker=lambda path, **kwargs: (_ for _ in ()).throw(RuntimeError("filter unavailable")))
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["perceptual_observations"] is None
    assert "filter unavailable" in result["perceptual_error"]


def test_preview_qc_rejects_bad_duration_and_report_overwrite(tmp_path):
    media = tmp_path / "preview.mp4"
    media.write_bytes(b"fake")
    timeline = {"plan_type": "editable_timeline", "scenes": [{"duration_seconds": float("nan")}]}
    with pytest.raises(ValueError, match="finite"):
        review_preview(media, timeline, technical_checker=lambda *args, **kwargs: {})
    report = tmp_path / "report.json"
    report.write_text("existing")
    timeline["scenes"][0]["duration_seconds"] = 2
    with pytest.raises(ValueError, match="already exists"):
        review_preview(media, timeline, report_path=report, technical_checker=lambda *args, **kwargs: {"passed": True}, perceptual_checker=lambda *args, **kwargs: {})


def test_preview_qc_captures_technical_tool_error_as_review_required(tmp_path):
    media = tmp_path / "preview.mp4"
    media.write_bytes(b"fake")
    timeline = {"plan_type": "editable_timeline", "scenes": [{"duration_seconds": 1}]}
    result = review_preview(media, timeline,
        technical_checker=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ffprobe missing")),
        perceptual_checker=lambda *args, **kwargs: {"observations": {}})
    assert result["status"] == "REVIEW_REQUIRED"
    assert "ffprobe missing" in result["technical_error"]


def test_preview_qc_rejects_substantially_truncated_preview_duration(tmp_path):
    media = tmp_path / "preview.mp4"
    media.write_bytes(b"fake")
    timeline = {"plan_type": "editable_timeline", "scenes": [{"duration_seconds": 10}]}
    received = {}
    def technical(path, **kwargs):
        received.update(kwargs)
        return {"passed": False, "problems": ["duration 5.000s is below minimum 9.000s"]}
    result = review_preview(media, timeline, technical_checker=technical,
        perceptual_checker=lambda path, **kwargs: {"observations": {}})
    assert received["min_duration"] == 9.0
    assert received["max_duration"] == 11.0
    assert result["status"] == "REVIEW_REQUIRED"
    assert "below minimum" in result["technical"]["problems"][0]
