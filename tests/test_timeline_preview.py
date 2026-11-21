from scripts.timeline_preview import resolve_scene_preview_path


def test_resolves_local_image(tmp_path):
    image = tmp_path / "still.jpg"
    image.write_bytes(b"fake image bytes")
    path, kind = resolve_scene_preview_path(str(image))
    assert path == image.resolve()
    assert kind == "image"


def test_resolves_local_video(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    path, kind = resolve_scene_preview_path(str(video))
    assert path == video.resolve()
    assert kind == "video"


def test_empty_missing_and_unsupported_paths_return_messages(tmp_path):
    assert resolve_scene_preview_path("") == (None, "Esta escena no tiene recurso asignado.")
    missing, _ = resolve_scene_preview_path(str(tmp_path / "absent.png"))
    assert missing is None
    unknown = tmp_path / "notes.txt"
    unknown.write_text("text", encoding="utf-8")
    assert resolve_scene_preview_path(str(unknown))[0] is None


def test_symlink_is_not_previewed(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"")
    link = tmp_path / "link.png"
    try:
        link.symlink_to(source)
    except OSError:
        return
    assert resolve_scene_preview_path(str(link))[0] is None
