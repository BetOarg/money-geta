from pathlib import Path

from scripts.subtitle_quality import evaluate_subtitles, inspect_subtitles, parse_subtitles


def test_srt_parses_and_accepts_valid_cues(tmp_path: Path) -> None:
    f = tmp_path / "sample.srt"
    f.write_text("1\n00:00:01,000 --> 00:00:03,000\nHello world.\n\n2\n00:00:03,200 --> 00:00:05,000\nSecond line.\n", encoding="utf-8")
    report = inspect_subtitles(f)
    assert report["passed"]
    assert report["cue_count"] == 2


def test_vtt_short_timestamps_parse(tmp_path: Path) -> None:
    f = tmp_path / "sample.vtt"
    f.write_text("WEBVTT\n\n00:01.000 --> 00:03.000\nHi there!\n", encoding="utf-8")
    cues = parse_subtitles(f)
    assert len(cues) == 1
    assert cues[0]["start"] == 1


def test_overlap_long_lines_and_fast_reading_fail() -> None:
    cues = [
        {"start": 0, "end": 1, "text": "This is an extremely long caption line that exceeds limits."},
        {"start": 0.5, "end": 1.5, "text": "Overlapping cue."},
    ]
    problems = evaluate_subtitles(cues)
    assert any("overlaps" in p for p in problems)
    assert any("exceeds" in p for p in problems)
    assert any("reading speed" in p for p in problems)


def test_no_cues_and_bad_file_fail(tmp_path: Path) -> None:
    assert evaluate_subtitles([]) == ["no subtitle cues found"]
    report = inspect_subtitles(tmp_path / "absent.srt")
    assert report["passed"] is False


def test_malformed_cue_block_is_not_silently_ignored(tmp_path: Path) -> None:
    f = tmp_path / "broken.srt"
    f.write_text(
        "1\\n00:00:01,000 --> 00:00:03,000\\nValid cue.\\n\\n"
        "2\\n00:00:04,000 - -> 00:00:06,000\\nBroken cue.\\n",
        encoding="utf-8",
    )
    report = inspect_subtitles(f)
    assert report["passed"] is False
    assert report["cue_count"] == 0
    assert any("malformed timing line" in issue for issue in report["problems"])


def test_vtt_note_metadata_is_ignored_and_valid_cue_passes(tmp_path: Path) -> None:
    f = tmp_path / "sample.vtt"
    f.write_text(
        "WEBVTT\\n\\nNOTE This is metadata\\nignored note text\\n\\n"
        "00:01.000 --> 00:03.000\\nValid cue.\\n",
        encoding="utf-8",
    )
    report = inspect_subtitles(f)
    assert report["passed"]
    assert report["cue_count"] == 1
