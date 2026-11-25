"""Fail-closed technical QC for rendered media using FFprobe and optional FFmpeg signal scans."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_media(path: Path, ffprobe: str | None = None, timeout: int = 30) -> dict[str, Any]:
    source = path.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"media file not found: {source}")
    if source.stat().st_size <= 0:
        raise ValueError("media file is empty")
    executable = ffprobe or shutil.which("ffprobe")
    if not executable:
        raise ValueError("ffprobe executable not found; install FFmpeg and add ffprobe to PATH")
    command = [executable, "-v", "error", "-show_entries",
               "format=duration,format_name,size:stream=index,codec_type,codec_name,width,height,avg_frame_rate",
               "-of", "json", str(source)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
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


def evaluate_media(payload: dict[str, Any], *, min_duration: float = 1.0,
                   max_duration: float | None = None, expected_aspect: str | None = None,
                   require_audio: bool = False) -> list[str]:
    problems = []
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
            elif abs(width / height - ratios[expected_aspect]) > 0.03:
                problems.append(f"aspect ratio {width}:{height} does not match {expected_aspect}")
        if not video[0].get("codec_name"):
            problems.append("video codec metadata is missing")
    return problems


def scan_signals(path: Path, *, ffmpeg: str | None = None, detect_black: bool = False,
                 detect_silence: bool = False, detect_clipping: bool = False,
                 timeout: int = 180) -> dict[str, Any]:
    """Run read-only FFmpeg black-frame, silence and clipping detectors; findings require human review."""
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise ValueError("ffmpeg executable not found; signal QC was requested")
    video_filter = "blackdetect=d=0.5:pix_th=0.10" if detect_black else "null"
    audio_filters = []
    if detect_silence:
        audio_filters.append("silencedetect=noise=-50dB:d=1.0")
    if detect_clipping:
        audio_filters.append("astats=metadata=1:reset=0")
    if not detect_black and not audio_filters:
        return {"black_segments": [], "silence_segments": [],
                "clipped_sample_counts": [], "clipping_detected": False}
    command = [executable, "-hide_banner", "-nostats", "-i", str(path), "-vf", video_filter]
    if audio_filters:
        command += ["-af", ",".join(audio_filters)]
    command += ["-f", "null", "-"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"FFmpeg signal scan timed out after {timeout} seconds") from exc
    except OSError as exc:
        raise ValueError(f"could not execute FFmpeg signal scan: {exc}") from exc
    if result.returncode != 0:
        raise ValueError("FFmpeg signal scan failed; signal QC cannot be marked complete")
    log = (result.stderr or "") + "\n" + (result.stdout or "")
    black = []
    silence = []
    if detect_black:
        for match in re.finditer(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)", log):
            black.append({"start": float(match.group(1)), "end": float(match.group(2)),
                          "duration": float(match.group(3))})
    if detect_silence:
        starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", log)]
        ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", log)]
        for index, start in enumerate(starts):
            end = ends[index] if index < len(ends) else None
            silence.append({"start": start, "end": end,
                            "duration": round(end - start, 3) if end is not None else None})
    clipped_counts = []
    if detect_clipping:
        clipped_counts = [int(value) for value in re.findall(r"Number of samples clipped:\\s*([0-9]+)", log, re.I)]
        if not clipped_counts:
            raise ValueError("FFmpeg astats did not report clipping sample counts")
    return {"black_segments": black, "silence_segments": silence,
            "clipped_sample_counts": clipped_counts,
            "clipping_detected": any(value > 0 for value in clipped_counts)}


def inspect_media(path: Path, *, ffprobe: str | None = None, timeout: int = 30,
                  min_duration: float = 1.0, max_duration: float | None = None,
                  expected_aspect: str | None = None, require_audio: bool = False,
                  ffmpeg: str | None = None, detect_black: bool = False,
                  detect_silence: bool = False, detect_clipping: bool = False) -> dict[str, Any]:
    source = path.expanduser().resolve()
    payload = probe_media(source, ffprobe=ffprobe, timeout=timeout)
    problems = evaluate_media(payload, min_duration=min_duration, max_duration=max_duration,
                              expected_aspect=expected_aspect, require_audio=require_audio)
    observations = scan_signals(source, ffmpeg=ffmpeg, detect_black=detect_black,
                                detect_silence=detect_silence, detect_clipping=detect_clipping,
                                timeout=max(timeout, 180))
    return {"schema_version": 1, "file": str(source), "sha256": sha256_file(source),
            "passed": not problems, "problems": problems, "observations": observations,
            "probe": payload,
            "scope": "technical checks only; signal findings require human review and do not certify editorial, factual, legal, rights, or platform clearance"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--ffprobe")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--min-duration", type=float, default=1.0)
    parser.add_argument("--max-duration", type=float)
    parser.add_argument("--aspect", choices=("9:16", "16:9", "1:1"))
    parser.add_argument("--require-audio", action="store_true")
    parser.add_argument("--detect-black", action="store_true")
    parser.add_argument("--detect-silence", action="store_true")
    parser.add_argument("--detect-clipping", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect_media(args.file, ffprobe=args.ffprobe, timeout=args.timeout,
                               min_duration=args.min_duration, max_duration=args.max_duration,
                               expected_aspect=args.aspect, require_audio=args.require_audio,
                               ffmpeg=args.ffmpeg, detect_black=args.detect_black,
                               detect_silence=args.detect_silence,
                               detect_clipping=args.detect_clipping)
    except (OSError, ValueError) as exc:
        report = {"schema_version": 1, "file": str(args.file), "passed": False,
                  "problems": [str(exc)], "observations": {},
                  "scope": "technical media checks only"}
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.report:
        destination = args.report.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized + "\n", encoding="utf-8")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
