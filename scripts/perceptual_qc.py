"""Perceptual media observations via FFmpeg blackdetect/freezedetect/silencedetect."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

BLACK_RE = re.compile(r"black_start:(-?\d+(?:\.\d+)?)\s+black_end:(-?\d+(?:\.\d+)?)\s+black_duration:(-?\d+(?:\.\d+)?)")
FREEZE_RE = re.compile(r"freeze_start:(-?\d+(?:\.\d+)?)\s+freeze_duration:(-?\d+(?:\.\d+)?)\s+freeze_end:(-?\d+(?:\.\d+)?)")
SILENCE_RE = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
SILENCE_END_RE = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(-?\d+(?:\.\d+)?)")


def analyze(path: Path, *, black_min: float = 1.0, freeze_min: float = 2.0,
            silence_min: float = 3.0, timeout: int = 120) -> dict:
    if not path.is_file():
        raise ValueError(f"Input file does not exist: {path}")
    if timeout < 1 or black_min < 0 or freeze_min < 0 or silence_min < 0:
        raise ValueError("Thresholds must be non-negative and timeout positive")
    filters = (
        f"blackdetect=d=0.10:pix_th=0.10:duration={black_min},"
        f"freezedetect=n=-60dB:d={freeze_min},"
        f"silencedetect=n=-50dB:d={silence_min}"
    )
    command = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vf", filters,
               "-af", f"silencedetect=n=-50dB:d={silence_min}", "-f", "null", "-"]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"FFmpeg timed out after {timeout}s") from exc
    log = (proc.stderr or "") + "\n" + (proc.stdout or "")
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed with exit code {proc.returncode}")
    black = [{"start": float(a), "end": float(b), "duration": float(c)}
              for a, b, c in BLACK_RE.findall(log)]
    freezes = [{"start": float(a), "duration": float(b), "end": float(c)}
               for a, b, c in FREEZE_RE.findall(log)]
    silence_starts = [float(x) for x in SILENCE_RE.findall(log)]
    silence_ends = [{"end": float(a), "duration": float(b)}
                    for a, b in SILENCE_END_RE.findall(log)]
    return {
        "schema_version": 1, "file": str(path), "mode": "observational",
        "thresholds": {"black_min_seconds": black_min, "freeze_min_seconds": freeze_min,
                       "silence_min_seconds": silence_min, "black_luma_threshold": 0.10,
                       "freeze_noise_threshold": "-60dB", "silence_noise_threshold": "-50dB"},
        "observations": {"black_segments": black, "freeze_segments": freezes,
                         "silence_starts": silence_starts, "silence_segments_ended": silence_ends},
        "note": "Observations are not defects by themselves; intentional black, stills, and silence may be valid."
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Observational perceptual QC for black frames, freezes and silence.")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--black-min", type=float, default=1.0, help="Minimum black segment duration in seconds")
    parser.add_argument("--freeze-min", type=float, default=2.0, help="Minimum freeze duration in seconds")
    parser.add_argument("--silence-min", type=float, default=3.0, help="Minimum silence duration in seconds")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--report", type=Path, help="Optional JSON report destination")
    args = parser.parse_args(argv)
    try:
        report = analyze(args.file, black_min=args.black_min, freeze_min=args.freeze_min,
                        silence_min=args.silence_min, timeout=args.timeout)
    except (ValueError, RuntimeError) as exc:
        print(f"Perceptual QC error: {exc}")
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
