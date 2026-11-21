"""Fail-closed technical QC for rendered media using FFprobe.

This checks container/stream integrity and basic delivery constraints only.
It does not assess editorial quality, factual accuracy, rights, or platform policy.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def probe_media(path: Path, ffprobe: str | None = None, timeout: int = 30) -> dict[str, Any]:
    source = path.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"media file not found: {source}")
    if source.stat().st_size <= 0:
        raise ValueError("media file is empty")
    executable = ffprobe or shutil.which("ffprobe")
    if not executable:
        raise ValueError("ffprobe executable not found; install FFmpeg and add ffprobe to PATH")
    command = [
        executable, "-v", "error", "-show_entries",
        "format=duration,format_name,size:stream=index,codec_type,codec_name,width,height,avg_frame_rate",
        "-of", "json", str(source),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"ffprobe timed out after {timeout} seconds") from exc
    except OSError as exc:
        raise ValueError(f"could not execute ffprobe: {exc}") from exc
    if result.returncode != 0:
        raise ValueError("ffprobe could not parse media; file may be corrupt or unsupported")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("ffprobe returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("ffprobe returned an invalid media description")
    return payload


def evaluate_media(
    payload: dict[str, Any],
    *,
    min_duration: float = 1.0,
    max_duration: float | None = None,
    expected_aspect: str | None = None,
    require_audio: bool = False,
) -> list[str]:
    problems: list[str] = []
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return ["media has no readable stream list"]
    video = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"]
    audio = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"]
    if not video:
        problems.append("media has no video stream")
    if require_audio and not audio:
        problems.append("media has no audio stream")

    fmt = payload.get("format")
    if not isinstance(fmt, dict):
        problems.append("media format metadata is missing")
        return problems
    try:
        duration = float(fmt.get("duration"))
    except (TypeError, ValueError):
        duration = 0.0
    if duration < min_duration:
        problems.append(f"duration {duration:.3f}s is below minimum {min_duration:.3f}s")
    if max_duration is not None and duration > max_duration:
        problems.append(f"duration {duration:.3f}s exceeds maximum {max_duration:.3f}s")

    if video:
        width, height = video[0].get("width"), video[0].get("height")
        if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
            problems.append("video dimensions are missing or invalid")
        elif expected_aspect:
            ratios = {"9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1.0}
            if expected_aspect not in ratios:
                problems.append(f"unsupported expected aspect ratio: {expected_aspect}")
            else:
                actual = width / height
                if abs(actual - ratios[expected_aspect]) > 0.03:
                    problems.append(
                        f"aspect ratio {width}:{height} does not match {expected_aspect}"
                    )
        if not video[0].get("codec_name"):
            problems.append("video codec metadata is missing")
    return problems


def inspect_media(
    path: Path,
    *,
    ffprobe: str | None = None,
    timeout: int = 30,
    min_duration: float = 1.0,
    max_duration: float | None = None,
    expected_aspect: str | None = None,
    require_audio: bool = False,
) -> dict[str, Any]:
    payload = probe_media(path, ffprobe=ffprobe, timeout=timeout)
    problems = evaluate_media(
        payload, min_duration=min_duration, max_duration=max_duration,
        expected_aspect=expected_aspect, require_audio=require_audio,
    )
    return {
        "schema_version": 1,
        "file": str(path.expanduser().resolve()),
        "passed": not problems,
        "problems": problems,
        "probe": payload,
        "scope": "technical media checks only; not editorial, factual, legal, rights, or platform clearance",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--ffprobe")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--min-duration", type=float, default=1.0)
    parser.add_argument("--max-duration", type=float)
    parser.add_argument("--aspect", choices=("9:16", "16:9", "1:1"))
    parser.add_argument("--require-audio", action="store_true")
    parser.add_argument("--report", type=Path, help="optional JSON report destination")
    args = parser.parse_args(argv)
    try:
        report = inspect_media(
            args.file, ffprobe=args.ffprobe, timeout=args.timeout,
            min_duration=args.min_duration, max_duration=args.max_duration,
            expected_aspect=args.aspect, require_audio=args.require_audio,
        )
    except (OSError, ValueError) as exc:
        report = {
            "schema_version": 1, "file": str(args.file), "passed": False,
            "problems": [str(exc)],
            "scope": "technical media checks only; not editorial, factual, legal, rights, or platform clearance",
        }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.report:
        destination = args.report.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized + "\n", encoding="utf-8")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
