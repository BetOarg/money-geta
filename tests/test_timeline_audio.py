import pytest
from scripts.timeline_audio import validate_audio_track, update_audio_track, remove_audio_track


def test_audio_track_metadata_only_and_normalized():
    draft = {"audio_tracks": []}
    updated = update_audio_track(draft, 0, {"name":"Music", "start_seconds":0, "duration_seconds":15, "volume":0.4, "fade_in_seconds":2, "fade_out_seconds":3})
    assert updated["audio_tracks"][0]["volume"] == 0.4
    assert updated["audio_tracks"][0]["source_path"] == ""
    assert draft["audio_tracks"] == []


def test_validate_audio_file_path_and_project_containment(tmp_path):
    source=tmp_path/"music.wav"; source.write_bytes(b"audio")
    normalized=validate_audio_track({"name":"Music","source_path":str(source),"start_seconds":1,"duration_seconds":10},project_root=tmp_path)
    assert normalized["source_path"]==str(source.resolve())
    outside=tmp_path.parent/"outside.wav"; outside.write_bytes(b"audio")
    with pytest.raises(ValueError,match="inside the project"):
        validate_audio_track({"name":"Music","source_path":str(outside),"duration_seconds":10},project_root=tmp_path)


def test_rejects_unsupported_or_missing_audio(tmp_path):
    bad=tmp_path/"notes.txt"; bad.write_text("x")
    with pytest.raises(ValueError,match="supported local audio"):
        validate_audio_track({"name":"bad","source_path":str(bad),"duration_seconds":5})
    with pytest.raises(ValueError,match="missing or inaccessible"):
        validate_audio_track({"name":"bad","source_path":str(tmp_path/"none.wav"),"duration_seconds":5})


def test_validates_audio_ranges_and_fades():
    with pytest.raises(ValueError,match="out of range"):
        validate_audio_track({"name":"music","duration_seconds":3,"volume":3})
    with pytest.raises(ValueError,match="cannot exceed"):
        validate_audio_track({"name":"music","duration_seconds":3,"fade_in_seconds":2,"fade_out_seconds":2})


def test_remove_audio_track():
    t={"audio_tracks":[{"name":"A"},{"name":"B"}]}
    assert remove_audio_track(t,0)["audio_tracks"]==[{"name":"B"}]
    with pytest.raises(ValueError,match="out of range"):
        remove_audio_track(t,4)
