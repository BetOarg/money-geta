"""Local structural and readability checks for SRT/WebVTT subtitles."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_TIME = re.compile(r"^((?:\d{2,}:\d{2}:\d{2}|\d{2,}:\d{2})[,.]\d{3})\s*-->\s*((?:\d{2,}:\d{2}:\d{2}|\d{2,}:\d{2})[,.]\d{3})(?:\s+.*)?$")
_TAG = re.compile(r"<[^>]+>")


def _seconds(value: str) -> float:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError("invalid timestamp")
    if int(minutes) >= 60 or float(seconds) >= 60:
        raise ValueError("timestamp minute/second fields must be below 60")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_subtitles(path: Path) -> list[dict[str, Any]]:
    text = path.expanduser().read_text(encoding="utf-8-sig")
    cues: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n")):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper().startswith("WEBVTT"):
            continue
        timing_index = next((i for i, line in enumerate(lines) if _TIME.match(line)), None)
        if timing_index is None:
            continue
        match = _TIME.match(lines[timing_index])
        assert match is not None
        caption_lines = lines[timing_index + 1:]
        caption_text = "\n".join(caption_lines)
        cues.append({
            "start": _seconds(match.group(1)), "end": _seconds(match.group(2)),
            "text": caption_text, "line_count": len(caption_lines),
            "line_lengths": [len(_TAG.sub("", line)) for line in caption_lines],
        })
    return cues


def evaluate_subtitles(cues: list[dict[str, Any]], *, max_line_chars: int = 42,
                      max_lines: int = 2, max_chars_per_second: float = 25.0,
                      min_cue_duration: float = 0.25, max_cue_duration: float = 8.0) -> list[str]:
    issues: list[str] = []
    if not cues:
        return ["no subtitle cues found"]
    previous_end = -1.0
    for index, cue in enumerate(cues, start=1):
        start, end = cue.get("start"), cue.get("end")
        text = str(cue.get("text", "")).strip()
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            issues.append(f"cue {index}: invalid timestamp values")
            continue
        duration = end - start
        if start < 0 or duration <= 0:
            issues.append(f"cue {index}: start/end timestamps are invalid")
        if start < previous_end:
            issues.append(f"cue {index}: overlaps previous cue")
        previous_end = max(previous_end, end)
        if duration < min_cue_duration:
            issues.append(f"cue {index}: duration is below {min_cue_duration:.2f}s")
        if duration > max_cue_duration:
            issues.append(f"cue {index}: duration exceeds {max_cue_duration:.2f}s")
        if not text:
            issues.append(f"cue {index}: caption text is empty")
        lines = text.splitlines()
        if len(lines) > max_lines:
            issues.append(f"cue {index}: has more than {max_lines} lines")
        for line_num, line in enumerate(lines, start=1):
            visible = _TAG.sub("", line).strip()
            if len(visible) > max_line_chars:
                issues.append(f"cue {index} line {line_num}: exceeds {max_line_chars} characters")
        visible_text = "".join(_TAG.sub("", line).strip() for line in lines)
        if duration > 0 and len(visible_text) / duration > max_chars_per_second:
            issues.append(f"cue {index}: reading speed exceeds {max_chars_per_second:.1f} chars/sec")
    return issues


def inspect_subtitles(path: Path, **limits: Any) -> dict[str, Any]:
    try:
        cues = parse_subtitles(path)
        issues = evaluate_subtitles(cues, **limits)
        return {"schema_version": 1, "file": str(path.expanduser().resolve()),
                "passed": not issues, "cue_count": len(cues), "problems": issues,
                "scope": "subtitle structure/readability only; does not verify transcription, translation or timing against audio"}
    except (OSError, UnicodeError, ValueError) as exc:
        return {"schema_version": 1, "file": str(path), "passed": False,
                "cue_count": 0, "problems": [str(exc)],
                "scope": "subtitle structure/readability only; does not verify transcription, translation or timing against audio"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--max-line-chars", type=int, default=42)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("--max-cps", type=float, default=25.0)
    parser.add_argument("--min-cue-duration", type=float, default=0.25)
    parser.add_argument("--max-cue-duration", type=float, default=8.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report = inspect_subtitles(args.file, max_line_chars=args.max_line_chars, max_lines=args.max_lines,
        max_chars_per_second=args.max_cps, min_cue_duration=args.min_cue_duration,
        max_cue_duration=args.max_cue_duration)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
