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
    assert "-c" in calls[1] and "copy" in calls[1]
    assert str(result) in calls[1]


def test_preview_rejects_non_cut_transition(tmp_path):
    plan = draft(tmp_path)
    plan["scenes"][0].update(transition_in="wipe", transition_duration_seconds=0.5)
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


def test_preview_mixes_local_audio_with_volume_delay_and_fades(tmp_path):
    plan = draft(tmp_path)
    soundtrack = tmp_path / "music.wav"
    soundtrack.write_bytes(b"placeholder")
    plan["audio_tracks"] = [{
        "name": "Background",
        "source_path": str(soundtrack),
        "start_seconds": 1.5,
        "duration_seconds": 2.5,
        "volume": 0.3,
        "fade_in_seconds": 0.5,
        "fade_out_seconds": 0.4,
    }]
    calls = []
    compose_preview(plan, tmp_path / "mixed-preview.mp4", ffmpeg="fake",
                   runner=lambda cmd, **kw: (calls.append(cmd) or success_runner(cmd, **kw)))
    assert len(calls) == 3
    assert calls[1][-1].endswith("video_only.mp4")
    mix = calls[2]
    filter_graph = mix[mix.index("-filter_complex") + 1]
    assert "volume=0.300" in filter_graph
    assert "afade=t=in:st=0:d=0.500" in filter_graph
    assert "afade=t=out:st=2.100:d=0.400" in filter_graph
    assert "adelay=delays=1500:all=1" in filter_graph
    assert "[mixed]" in mix
    assert str(tmp_path / "mixed-preview.mp4") in mix


def test_preview_rejects_audio_tracks_without_local_source(tmp_path):
    plan = draft(tmp_path)
    plan["audio_tracks"] = [{
        "name": "Unresolved",
        "source_path": "",
        "start_seconds": 0,
        "duration_seconds": 1,
        "volume": 1,
        "fade_in_seconds": 0,
        "fade_out_seconds": 0,
    }]
    with pytest.raises(ValueError, match="local source file"):
        compose_preview(plan, tmp_path / "out.mp4", ffmpeg="fake", runner=success_runner)


def test_preview_renders_fade_and_dissolve_xfade_filters(tmp_path):
    plan = draft(tmp_path)
    second = tmp_path / "still-2.png"
    second.write_bytes(b"placeholder")
    plan["scenes"].append({
        "scene_id": "scene-002", "duration_seconds": 4,
        "visual_path": str(second), "subtitle_text": "Second",
        "transition_in": "fade", "transition_duration_seconds": 0.75,
    })
    calls = []
    compose_preview(plan, tmp_path / "transitions.mp4", ffmpeg="fake",
                   runner=lambda cmd, **kw: (calls.append(cmd) or success_runner(cmd, **kw)))
    assert len(calls) == 3
    graph = calls[-1][calls[-1].index("-filter_complex") + 1]
    assert "xfade=transition=fade:duration=0.750:offset=2.250" in graph
    assert "-map" in calls[-1] and "[v1]" in calls[-1]


def test_preview_cut_groups_concat_and_transition_duration_validation(tmp_path):
    plan = draft(tmp_path)
    second = tmp_path / "still-2.png"
    second.write_bytes(b"placeholder")
    third = tmp_path / "still-3.png"
    third.write_bytes(b"placeholder")
    plan["scenes"].extend([
        {"scene_id": "scene-002", "duration_seconds": 2, "visual_path": str(second),
         "subtitle_text": "", "transition_in": "cut", "transition_duration_seconds": 0},
        {"scene_id": "scene-003", "duration_seconds": 2, "visual_path": str(third),
         "subtitle_text": "", "transition_in": "dissolve", "transition_duration_seconds": 1},
    ])
    calls = []
    compose_preview(plan, tmp_path / "mixed-cuts.mp4", ffmpeg="fake",
                   runner=lambda cmd, **kw: (calls.append(cmd) or success_runner(cmd, **kw)))
    assert any("concat" in cmd and "group_0001.txt" in str(cmd) for cmd in calls)
    assert any("transition=dissolve" in str(cmd) for cmd in calls)
    plan["scenes"][2]["transition_duration_seconds"] = 5
    with pytest.raises(ValueError, match="fit inside"):
        compose_preview(plan, tmp_path / "invalid-transition.mp4", ffmpeg="fake", runner=success_runner)


def test_first_scene_cannot_have_incoming_transition(tmp_path):
    plan = draft(tmp_path)
    plan["scenes"][0]["transition_in"] = "fade"
    plan["scenes"][0]["transition_duration_seconds"] = 0.5
    with pytest.raises(ValueError, match="first scene"):
        compose_preview(plan, tmp_path / "first-fade.mp4", ffmpeg="fake", runner=success_runner)
