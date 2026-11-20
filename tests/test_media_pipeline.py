import json
from pathlib import Path

import pytest

from scripts import media_pipeline


def test_inspect_media_parses_ffprobe_output(tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fake")
    monkeypatch.setattr(media_pipeline.shutil, "which", lambda name: "/usr/bin/ffprobe")
    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps({
            "format": {"duration": "12.5", "format_name": "mov,mp4"},
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
        })
    monkeypatch.setattr(media_pipeline, "_run", lambda *a, **k: Result())
    result = media_pipeline.inspect_media(source)
    assert result["duration_seconds"] == 12.5
    assert result["video"]["height"] == 1920
    assert result["audio"]["codec_name"] == "aac"


def test_inspect_media_requires_existing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        media_pipeline.inspect_media(tmp_path / "missing.mp4")


def test_scene_detection_fails_closed_without_pyscenedetect(tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fake")
    monkeypatch.setattr(media_pipeline.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="PySceneDetect"):
        media_pipeline.detect_scenes(source, tmp_path / "out")


def test_transcription_writes_srt_and_vtt(tmp_path, monkeypatch):
    source = tmp_path / "voice.mp4"
    source.write_bytes(b"fake")

    class Segment:
        start, end, text = 1.25, 2.5, "Hello world"

    class Info:
        language = "en"

    class Model:
        def __init__(self, *args, **kwargs):
            pass
        def transcribe(self, *args, **kwargs):
            return iter([Segment()]), Info()

    class Module:
        WhisperModel = Model

    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", Module())
    srt, vtt = media_pipeline.transcribe(source, tmp_path / "out")
    assert "00:00:01,250 --> 00:00:02,500" in srt.read_text(encoding="utf-8")
    assert "00:00:01.250 --> 00:00:02.500" in vtt.read_text(encoding="utf-8")
    metadata = json.loads((tmp_path / "out" / "voice-transcription.json").read_text())
    assert metadata["segments"] == 1


def test_burn_subtitles_requires_inputs(tmp_path):
    with pytest.raises(FileNotFoundError):
        media_pipeline.burn_subtitles(tmp_path / "missing.mp4", tmp_path / "missing.srt", tmp_path / "out.mp4")



def test_scene_detection_uses_supported_pyscenedetect_cli_order(tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fake")
    output = tmp_path / "out"
    monkeypatch.setattr(media_pipeline.shutil, "which", lambda name: "/usr/bin/scenedetect")
    captured = {}
    class Result:
        returncode = 0
        stderr = ""
    def fake_run(command, **kwargs):
        captured["command"] = command
        output.mkdir(parents=True, exist_ok=True)
        (output / "input-scenes.csv").write_text("Scene Number,Start Timecode\\n", encoding="utf-8")
        return Result()
    monkeypatch.setattr(media_pipeline, "_run", fake_run)
    result = media_pipeline.detect_scenes(source, output, 25)
    command = captured["command"]
    assert command.index("--input") < command.index("detect-content") < command.index("list-scenes")
    assert command[command.index("--threshold") + 1] == "25"
    assert result.name == "input-scenes.csv"
