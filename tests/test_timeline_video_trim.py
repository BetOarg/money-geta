
def test_update_scene_supports_valid_video_trim_and_preview_start(tmp_path):
    from scripts.timeline_plan import update_scene
    from scripts.timeline_preview import resolve_scene_preview_path
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    timeline = {"scenes": [{"visual_path": str(clip), "duration_seconds": 5}]}
    updated = update_scene(timeline, 0, trim_start_seconds=2.5, trim_end_seconds=7.0)
    scene = updated["scenes"][0]
    assert scene["media_trim_start_seconds"] == 2.5
    assert scene["media_trim_end_seconds"] == 7.0
    assert resolve_scene_preview_path(scene["visual_path"])[1] == "video"


def test_update_scene_rejects_invalid_trim_bounds_and_image_trim(tmp_path):
    from scripts.timeline_plan import update_scene
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    image = tmp_path / "still.png"
    image.write_bytes(b"image")
    timeline = {"scenes": [{"visual_path": str(clip), "duration_seconds": 5}]}
    with pytest.raises(ValueError, match="greater than start"):
        update_scene(timeline, 0, trim_start_seconds=3, trim_end_seconds=2)
    with pytest.raises(ValueError, match="non-negative"):
        update_scene(timeline, 0, trim_start_seconds=-1, trim_end_seconds=None)
    image_timeline = {"scenes": [{"visual_path": str(image), "duration_seconds": 5}]}
    with pytest.raises(ValueError, match="only available for local video"):
        update_scene(image_timeline, 0, trim_start_seconds=1, trim_end_seconds=None)


def test_update_scene_can_clear_trim():
    from scripts.timeline_plan import update_scene
    timeline = {"scenes": [{
        "visual_path": "/tmp/video.mp4", "duration_seconds": 5,
        "media_trim_start_seconds": 1, "media_trim_end_seconds": 4,
    }]}
    updated = update_scene(timeline, 0, trim_start_seconds=0, trim_end_seconds=None)
    assert "media_trim_start_seconds" not in updated["scenes"][0]
    assert "media_trim_end_seconds" not in updated["scenes"][0]
