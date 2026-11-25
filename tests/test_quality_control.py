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


def test_signal_scan_parses_black_and_silence_findings(tmp_path, monkeypatch):
    import subprocess
    import scripts.quality_control as qc

    source = tmp_path / "sample.mp4"
    source.write_bytes(b"media")
    def fake_run(command, **kwargs):
        assert "blackdetect=d=0.5:pix_th=0.10" in command
        assert "silencedetect=noise=-50dB:d=1.0" in command
        return subprocess.CompletedProcess(command, 0, "", (
            "[blackdetect] black_start:1.000 black_end:2.500 black_duration:1.500\n"
            "[silencedetect] silence_start:3.000\n"
            "[silencedetect] silence_end:4.250 | silence_duration:1.250\n"
        ))
    monkeypatch.setattr(qc.subprocess, "run", fake_run)
    result = qc.scan_signals(source, ffmpeg="ffmpeg", detect_black=True, detect_silence=True)
    assert result["black_segments"] == [{"start": 1.0, "end": 2.5, "duration": 1.5}]
    assert result["silence_segments"] == [{"start": 3.0, "end": 4.25, "duration": 1.25}]


def test_signal_scan_fails_closed_when_ffmpeg_fails(tmp_path, monkeypatch):
    import subprocess
    import scripts.quality_control as qc

    source = tmp_path / "sample.mp4"
    source.write_bytes(b"media")
    monkeypatch.setattr(qc.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", "decode error"))
    import pytest
    with pytest.raises(ValueError, match="signal scan failed"):
        qc.scan_signals(source, ffmpeg="ffmpeg", detect_black=True)


def test_signal_scan_requires_ffmpeg_when_enabled(tmp_path, monkeypatch):
    import scripts.quality_control as qc
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"media")
    monkeypatch.setattr(qc.shutil, "which", lambda name: None)
    import pytest
    with pytest.raises(ValueError, match="ffmpeg executable not found"):
        qc.scan_signals(source, detect_silence=True)


def test_signal_scan_detects_clipped_audio_samples(tmp_path, monkeypatch):
    import subprocess
    import scripts.quality_control as qc

    source = tmp_path / "sample.mp4"
    source.write_bytes(b"media")
    def fake_run(command, **kwargs):
        assert "astats=metadata=1:reset=0" in command
        return subprocess.CompletedProcess(command, 0, "", (
            "Channel: 1\\nNumber of samples clipped: 12\\n"
            "Overall\\nNumber of samples clipped: 12\\n"
        ))
    monkeypatch.setattr(qc.subprocess, "run", fake_run)
    result = qc.scan_signals(source, ffmpeg="ffmpeg", detect_clipping=True)
    assert result["clipped_sample_counts"] == [12, 12]
    assert result["clipping_detected"] is True


def test_signal_scan_reports_zero_clipping(tmp_path, monkeypatch):
    import subprocess
    import scripts.quality_control as qc

    source = tmp_path / "sample.mp4"
    source.write_bytes(b"media")
    monkeypatch.setattr(
        qc.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, "", "Number of samples clipped: 0\\n"
        ),
    )
    result = qc.scan_signals(source, ffmpeg="ffmpeg", detect_clipping=True)
    assert result["clipped_sample_counts"] == [0]
    assert result["clipping_detected"] is False


def test_signal_scan_fails_closed_if_astats_has_no_clipping_metric(tmp_path, monkeypatch):
    import subprocess
    import scripts.quality_control as qc
    import pytest

    source = tmp_path / "sample.mp4"
    source.write_bytes(b"media")
    monkeypatch.setattr(
        qc.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", "no astats output"),
    )
    with pytest.raises(ValueError, match="did not report clipping sample counts"):
        qc.scan_signals(source, ffmpeg="ffmpeg", detect_clipping=True)
