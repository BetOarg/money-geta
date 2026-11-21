from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.timeline_composer import compose_preview


def draft(tmp_path):
    image = tmp_path / "still.png"
    image.write_bytes(b"fake-image")
    return {
        "plan_type": "editable_timeline",
        "render_authorized": False,
        "publishing_authorized": False,
        "scenes": [{
            "scene_id": "scene-001",
            "duration_seconds": 3,
            "visual_path": str(image),
            "subtitle_text": "Preview caption",
            "transition_in": "cut",
            "transition_duration_seconds": 0,
        }],
    }


def fake_runner(commands, **kwargs):
    # Capture commands and pretend FFmpeg succeeds. Test-only; no media is rendered.
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_preview_composer_builds_commands_for_local_draft(tmp_path):
    plan = draft(tmp_path)
    output = tmp_path / "preview.mp4"
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return fake_runner(command, **kwargs)
    result = compose_preview(plan, output, ffmpeg="ffmpeg-test", runner=runner)
    assert result == output.resolve()
    assert len(calls) == 2
    assert "-loop" in calls[0] and "subtitles=" in calls[0][-3]
    assert calls[1][calls[1].index("-f") + 1] == "concat"
    assert str(output) in calls[1]


def test_preview_rejects_non_cut_transitions(tmp_path):
    plan = draft(tmp_path)
    plan["scenes"][0]["transition_in"] = "fade"
    plan["scenes"][0]["transition_duration_seconds"] = 0.5
    with pytest.raises(ValueError, match="cuts only"):
        compose_preview(plan, tmp_path / "out.mp4", ffmpeg="ffmpeg-test", runner=fake_runner)


def test_preview_rejects_missing_media_and_existing_output(tmp_path):
    plan = draft(tmp_path)
    plan["scenes"][0]["visual_path"] = str(tmp_path / "missing.png")
    with pytest.raises(ValueError, match="valid local"):
        compose_preview(plan, tmp_path / "out.mp4", ffmpeg="ffmpeg-test", runner=fake_runner)
    plan = draft(tmp_path)
    existing = tmp_path / "out.mp4"
    existing.write_bytes(b"existing")
    with pytest.raises(ValueError, match="already exists"):
        compose_preview(plan, existing, ffmpeg="ffmpeg-test", runner=fake_runner)


def test_preview_requires_draft_and_rejects_authorized_render_flag(tmp_path):
    plan = draft(tmp_path)
    plan["render_authorized"] = True
    with pytest.raises(ValueError, match="draft timelines"):
        compose_preview(plan, tmp_path / "out.mp4", ffmpeg="ffmpeg-test", runner=fake_runner)
