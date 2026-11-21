import json
from pathlib import Path

from scripts.quality_control import evaluate_media, inspect_media, main, probe_media


GOOD = {
    "format": {"duration": "30.0", "format_name": "mov,mp4", "size": "1000"},
    "streams": [
        {"index": 0, "codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
        {"index": 1, "codec_type": "audio", "codec_name": "aac"},
    ],
}


def test_valid_vertical_media_passes():
    assert evaluate_media(GOOD, expected_aspect="9:16", require_audio=True) == []


def test_missing_video_stream_fails():
    payload = {"format": {"duration": "10"}, "streams": [{"codec_type": "audio"}]}
    problems = evaluate_media(payload)
    assert any("no video stream" in item for item in problems)


def test_missing_required_audio_fails():
    payload = {"format": {"duration": "10"}, "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080}
    ]}
    assert any("no audio stream" in item for item in evaluate_media(payload, require_audio=True))


def test_duration_and_aspect_limits_fail():
    problems = evaluate_media(GOOD, min_duration=45, expected_aspect="16:9")
    assert any("below minimum" in item for item in problems)
    assert any("does not match" in item for item in problems)


def test_probe_rejects_missing_file(tmp_path):
    try:
        probe_media(tmp_path / "missing.mp4", ffprobe="ffprobe")
    except ValueError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("missing media must fail closed")


def test_cli_writes_json_report_on_probe_failure(tmp_path):
    report = tmp_path / "qc.json"
    code = main(["--file", str(tmp_path / "missing.mp4"), "--report", str(report)])
    assert code == 2
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["passed"] is False
    assert data["problems"]
