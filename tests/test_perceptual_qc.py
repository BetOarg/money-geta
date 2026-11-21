from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import perceptual_qc


def test_analyze_parses_black_freeze_silence(monkeypatch, tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    stderr = """
black_start:1.000 black_end:2.500 black_duration:1.500
freeze_start:3.000 freeze_duration:2.500 freeze_end:5.500
silence_start:0.000
silence_end:4.000 | silence_duration:4.000
"""
    monkeypatch.setattr(perceptual_qc.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stderr=stderr, stdout=""))
    report = perceptual_qc.analyze(media)
    assert report["mode"] == "observational"
    assert report["observations"]["black_segments"] == [{"start": 1.0, "end": 2.5, "duration": 1.5}]
    assert report["observations"]["freeze_segments"] == [{"start": 3.0, "duration": 2.5, "end": 5.5}]
    assert report["observations"]["silence_starts"] == [0.0]
    assert report["observations"]["silence_segments_ended"] == [{"end": 4.0, "duration": 4.0}]


def test_missing_file_rejected(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        perceptual_qc.analyze(tmp_path / "missing.mp4")


def test_ffmpeg_failure_raises(monkeypatch, tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    monkeypatch.setattr(perceptual_qc.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stderr="bad input", stdout=""))
    with pytest.raises(RuntimeError, match="exit code 1"):
        perceptual_qc.analyze(media)


def test_threshold_validation(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    with pytest.raises(ValueError, match="Thresholds"):
        perceptual_qc.analyze(media, freeze_min=-1)
