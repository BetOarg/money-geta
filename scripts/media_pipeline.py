"""Optional local media analysis and subtitle tools for Money-Geta.

All media processing is local. External capture/downloader tools are intentionally
not invoked by this module: source acquisition requires a separate permission-aware
workflow and explicit operator action.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(command: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=capture, text=True, check=False)


def inspect_media(source: Path) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Media file not found: {source}")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not found on PATH")
    result = _run([
        ffprobe, "-v", "error", "-show_entries",
        "format=duration,format_name:stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of", "json", str(source),
    ])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    return {
        "source": str(source),
        "duration_seconds": float(payload.get("format", {}).get("duration", 0)),
        "format": payload.get("format", {}).get("format_name"),
        "video": video,
        "audio": audio,
    }


def detect_scenes(source: Path, output_dir: Path, threshold: float = 27.0) -> Path:
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Media file not found: {source}")
    executable = shutil.which("scenedetect")
    if not executable:
        raise RuntimeError("PySceneDetect CLI not found; install money-geta[media]")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = _run([
        executable, "--input", str(source), "detect-content",
        "--threshold", str(threshold), "list-scenes",
        "--output", str(output_dir), "--filename", "$VIDEO_NAME-scenes",
        "--format", "csv",
    ])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "PySceneDetect failed")
    csv_files = sorted(output_dir.glob("*-Scenes.csv")) + sorted(output_dir.glob("*-scenes.csv"))
    if not csv_files:
        # PySceneDetect versions differ in filename casing; return the generated CSV
        # only when exactly one CSV exists, otherwise avoid guessing.
        csv_files = sorted(output_dir.glob("*.csv"))
    if len(csv_files) != 1:
        raise RuntimeError(f"Expected one scene CSV, found {len(csv_files)}")
    return csv_files[0]


def _timestamp(seconds: float, separator: str = ",") -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def transcribe(source: Path, output_dir: Path, model_name: str = "small",
               language: str | None = None, device: str = "auto") -> tuple[Path, Path]:
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Media file not found: {source}")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed; install money-geta[media]") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(model_name, device=device, compute_type="int8" if device == "cpu" else "default")
    segments, info = model.transcribe(str(source), language=language, vad_filter=True)
    materialized = list(segments)
    stem = source.stem
    srt_path, vtt_path = output_dir / f"{stem}.srt", output_dir / f"{stem}.vtt"
    srt_lines, vtt_lines = [], ["WEBVTT", ""]
    for index, segment in enumerate(materialized, 1):
        text = segment.text.strip()
        srt_lines.extend([str(index), f"{_timestamp(segment.start)} --> {_timestamp(segment.end)}", text, ""])
        vtt_lines.extend([f"{_timestamp(segment.start, '.')} --> {_timestamp(segment.end, '.')}", text, ""])
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")
    metadata = {
        "source": str(source), "language": getattr(info, "language", language),
        "model": model_name, "segments": len(materialized),
        "srt": str(srt_path), "vtt": str(vtt_path),
    }
    (output_dir / f"{stem}-transcription.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return srt_path, vtt_path


def burn_subtitles(source: Path, subtitles: Path, output: Path) -> Path:
    source, subtitles, output = (p.expanduser().resolve() for p in (source, subtitles, output))
    if not source.is_file() or not subtitles.is_file():
        raise FileNotFoundError("Input video and subtitle file must both exist")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Escape drive-letter colon for FFmpeg's subtitles filter on Windows.
    subtitle_arg = str(subtitles).replace("\\", "/").replace(":", r"\\:")
    result = _run([
        ffmpeg, "-y", "-i", str(source), "-vf", f"subtitles='{subtitle_arg}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "copy", str(output),
    ])
    if result.returncode or not output.is_file():
        raise RuntimeError(result.stderr.strip() or "FFmpeg subtitle burn failed")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="money-geta media")
    commands = parser.add_subparsers(dest="action", required=True)
    inspect = commands.add_parser("inspect", help="read local media metadata with ffprobe")
    inspect.add_argument("--source", type=Path, required=True)
    scenes = commands.add_parser("scenes", help="detect scene boundaries with PySceneDetect")
    scenes.add_argument("--source", type=Path, required=True)
    scenes.add_argument("--output-dir", type=Path, required=True)
    scenes.add_argument("--threshold", type=float, default=27.0)
    speech = commands.add_parser("transcribe", help="create local SRT and VTT with faster-whisper")
    speech.add_argument("--source", type=Path, required=True)
    speech.add_argument("--output-dir", type=Path, required=True)
    speech.add_argument("--model", default="small")
    speech.add_argument("--language", default=None)
    speech.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    burn = commands.add_parser("burn-subtitles", help="burn an SRT/VTT subtitle file into a video")
    burn.add_argument("--source", type=Path, required=True)
    burn.add_argument("--subtitles", type=Path, required=True)
    burn.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "inspect":
            print(json.dumps(inspect_media(args.source), ensure_ascii=False, indent=2))
        elif args.action == "scenes":
            print(detect_scenes(args.source, args.output_dir, args.threshold))
        elif args.action == "transcribe":
            srt, vtt = transcribe(args.source, args.output_dir, args.model, args.language, args.device)
            print(f"SRT: {srt}\nVTT: {vtt}")
        elif args.action == "burn-subtitles":
            print(burn_subtitles(args.source, args.subtitles, args.output))
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
