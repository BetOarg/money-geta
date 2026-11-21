from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.timeline_composer import compose_preview


def draft(tmp_path):
    still = tmp_path / "still.png"
    still.write_bytes(b"placeholder")
    return {
        "plan_type": "editable_timeline",
        "render_authorized": False,
        "publishing_authorized": False,
        "scenes": [{
            "scene_id": "scene-001", "duration_seconds": 3,
            "visual_path": str(still), "subtitle_text": "Preview caption",
            "transition_in": "cut", "transition_duration_seconds": 0,
        }],
    }


def success_runner(command, **kwargs):
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_preview_composer_builds_segment_and_concat_commands(tmp_path):
    plan = draft(tmp_path)
    calls = []
    result = compose_preview(plan, tmp_path / "preview.mp4", ffmpeg="fake-ffmpeg",
                            runner=lambda cmd, **kw: (calls.append(cmd) or success_runner(cmd, **kw)))
    assert result == (tmp_path / "preview.mp4").resolve()
    assert len(calls) == 2
    assert "-loop" in calls[0]
    filter_string = calls[0][calls[0].index("-vf") + 1]
    assert "subtitles=" in filter_string and "scale=1080:1920" in filter_string
    assert calls[1][calls[1].index("-f") + 1] == "concat"
    assert str(result) in calls[1]


def test_preview_rejects_non_cut_transition(tmp_path):
    plan = draft(tmp_path)
    plan["scenes"][0].update(transition_in="fade", transition_duration_seconds=0.5)
    with pytest.raises(ValueError, match="cuts only"):
        compose_preview(plan, tmp_path / "preview.mp4", ffmpeg="fake", runner=success_runner)


def test_preview_rejects_missing_media_and_existing_output(tmp_path):
    plan = draft(tmp_path)
    plan["scenes"][0]["visual_path"] = str(tmp_path / "missing.mp4")
    with pytest.raises(ValueError, match="valid local"):
        compose_preview(plan, tmp_path / "out.mp4", ffmpeg="fake", runner=success_runner)
    plan = draft(tmp_path)
    existing = tmp_path / "out.mp4"
    existing.write_bytes(b"already here")
    with pytest.raises(ValueError, match="already exists"):
        compose_preview(plan, existing, ffmpeg="fake", runner=success_runner)


def test_preview_rejects_render_authorized_draft(tmp_path):
    plan = draft(tmp_path)
    plan["render_authorized"] = True
    with pytest.raises(ValueError, match="draft timelines"):
        compose_preview(plan, tmp_path / "out.mp4", ffmpeg="fake", runner=success_runner)


def test_srt_timestamp_supports_minutes_and_hours():
    from scripts.timeline_composer import _srt_timestamp
    assert _srt_timestamp(65.25) == "00:01:05,250"
    assert _srt_timestamp(3661.005) == "01:01:01,005"


def test_video_trim_and_padding_filters_are_applied(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"placeholder")
    plan = draft(tmp_path)
    plan["scenes"][0]["visual_path"] = str(clip)
    plan["scenes"][0]["media_trim_start_seconds"] = 1.0
    plan["scenes"][0]["media_trim_end_seconds"] = 2.5
    plan["scenes"][0]["duration_seconds"] = 3.0
    calls = []
    compose_preview(plan, tmp_path / "video-preview.mp4", ffmpeg="fake",
                   runner=lambda cmd, **kw: (calls.append(cmd) or success_runner(cmd, **kw)))
    filters = calls[0][calls[0].index("-vf") + 1]
    assert "trim=duration=1.500" in filters
    assert "tpad=stop_mode=clone:stop_duration=1.500" in filters
