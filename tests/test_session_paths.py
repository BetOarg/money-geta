from pathlib import Path

import pytest

from scripts.session_paths import create_session_dir, safe_job_id


def test_existing_session_files_are_preserved(tmp_path: Path) -> None:
    old = tmp_path / "job-1" / "live" / "previous-session"
    old.mkdir(parents=True)
    recording = old / "seg_0001.ts"
    recording.write_bytes(b"keep-me")

    new = create_session_dir(tmp_path, "job-1")

    assert new != old
    assert recording.read_bytes() == b"keep-me"
    assert new.is_dir()


def test_each_session_gets_a_new_directory(tmp_path: Path) -> None:
    first = create_session_dir(tmp_path, "job")
    second = create_session_dir(tmp_path, "job")
    assert first != second


@pytest.mark.parametrize("bad", ["", "...", "../escape", "../../x"])
def test_job_id_cannot_escape_root(bad: str, tmp_path: Path) -> None:
    if bad in {"", "..."}:
        with pytest.raises(ValueError):
            safe_job_id(bad)
    else:
        # Traversal characters are stripped/replaced into a single component.
        normalized = safe_job_id(bad)
        assert "/" not in normalized and "\\" not in normalized
        created = create_session_dir(tmp_path, bad)
        assert created.resolve().is_relative_to(tmp_path.resolve())
