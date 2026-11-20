"""Permission-gated source acquisition via the yt-dlp executable."""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def validate_source_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source URL must be an absolute HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not accepted")
    return value.strip()


def resolve_ffmpeg(override: Path | None = None) -> Path | None:
    if override:
        candidate = override.expanduser().resolve()
        if candidate.is_dir():
            candidate = candidate / ("ffmpeg.exe" if __import__("os").name == "nt" else "ffmpeg")
        if not candidate.is_file():
            raise FileNotFoundError(f"FFmpeg path not found: {candidate}")
        return candidate
    found = shutil.which("ffmpeg")
    if found:
        return Path(found).resolve()
    import os
    mpt_dir = os.environ.get("MONEYPRINTERTURBO_DIR")
    if mpt_dir:
        bundled = Path(mpt_dir).expanduser() / "lib/python/Lib/site-packages/imageio_ffmpeg/binaries"
        candidates = list(bundled.glob("ffmpeg*.exe")) if bundled.is_dir() else []
        if candidates:
            return candidates[0].resolve()
    return None


def download_source(url: str, output_dir: Path, ffmpeg_location: Path | None = None) -> Path:
    url = validate_source_url(url)
    executable = shutil.which("yt-dlp")
    if not executable:
        raise RuntimeError("yt-dlp not found on PATH; install yt-dlp before using source acquisition")
    ffmpeg = resolve_ffmpeg(ffmpeg_location)
    if ffmpeg is None:
        raise RuntimeError("FFmpeg not found on PATH; pass --ffmpeg-location or add FFmpeg to PATH")
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / "%(title).80B-%(id)s.%(ext)s")
    command = [
        executable, "--ignore-config", "--no-playlist", "--no-overwrites",
        "--no-progress", "--no-warnings", "--no-simulate",
        "--format", "bestvideo+bestaudio/best", "--merge-output-format", "mp4",
        "--ffmpeg-location", str(ffmpeg), "--output", template,
        "--print", "after_move:filepath", url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"yt-dlp exited with code {result.returncode}")
    candidates = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    if not candidates:
        raise RuntimeError("yt-dlp completed without reporting the final filepath")
    output = candidates[-1]
    if not output.is_absolute():
        output = output_dir / output
    output = output.resolve()
    try:
        output.relative_to(output_dir)
    except ValueError as exc:
        raise RuntimeError("yt-dlp reported an output outside the selected session directory") from exc
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"yt-dlp reported a missing or empty output: {output}")
    return output
