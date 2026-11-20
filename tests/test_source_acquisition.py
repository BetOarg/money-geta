from pathlib import Path

import pytest

from scripts import source_acquisition


def test_source_url_requires_http_or_https():
    assert source_acquisition.validate_source_url("https://example.test/video") == "https://example.test/video"
    with pytest.raises(ValueError):
        source_acquisition.validate_source_url("file:///C:/private.mp4")
    with pytest.raises(ValueError):
        source_acquisition.validate_source_url("https://user:pass@example.test/video")


def test_download_source_requires_ytdlp(tmp_path, monkeypatch):
    monkeypatch.setattr(source_acquisition.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="yt-dlp"):
        source_acquisition.download_source("https://example.test/video", tmp_path)


def test_download_source_verifies_output_and_scopes_to_session(tmp_path, monkeypatch):
    output_dir = tmp_path / "session"
    video = output_dir / "clip.mp4"
    monkeypatch.setattr(source_acquisition.shutil, "which", lambda name: "/usr/bin/yt-dlp" if name == "yt-dlp" else "/usr/bin/ffmpeg")
    captured = {}
    class Result:
        returncode = 0
        stderr = ""
        stdout = str(video) + "\n"
    def fake_run(command, **kwargs):
        captured["command"] = command
        output_dir.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"downloaded")
        return Result()
    monkeypatch.setattr(source_acquisition.subprocess, "run", fake_run)
    result = source_acquisition.download_source("https://example.test/video?token=secret", output_dir)
    assert result == video.resolve()
    assert "--ignore-config" in captured["command"]
    assert "--no-playlist" in captured["command"]
    assert "secret" in captured["command"][-1]
    assert str(output_dir.resolve()) in captured["command"][captured["command"].index("--output") + 1]


def test_download_source_rejects_output_outside_session(tmp_path, monkeypatch):
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"downloaded")
    output_dir = tmp_path / "session"
    monkeypatch.setattr(source_acquisition.shutil, "which", lambda name: "/usr/bin/yt-dlp" if name == "yt-dlp" else "/usr/bin/ffmpeg")
    class Result:
        returncode = 0
        stderr = ""
        stdout = str(outside) + "\n"
    monkeypatch.setattr(source_acquisition.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(RuntimeError, match="outside"):
        source_acquisition.download_source("https://example.test/video", output_dir)
