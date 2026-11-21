"""Local FFmpeg preview composer for editable timeline drafts.

This module intentionally renders preview files only. It never mutates timeline drafts,
authorizes final renders, or publishes/schedules media.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from scripts.timeline_plan import MIN_DURATION, MAX_DURATION

_TEXT_SAFE = re.compile(r"[^\\w\\s.,!?;:'\"()\\-–—%]+")


def _finite(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite.")
    return result


def _filter_path(path: Path) -> str:
    # Escape characters used by FFmpeg filter arguments, not shell syntax.
    return str(path.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def _subtitle_text(value: Any) -> str:
    # SRT is text, not executable filter input. Normalize line breaks and remove control chars.
    return "".join(ch for ch in str(value) if ch in "\\n\\t" or ord(ch) >= 32).strip()


def _validate_timeline(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(timeline, dict) or timeline.get("plan_type") != "editable_timeline":
        raise ValueError("An editable timeline draft is required.")
    if timeline.get("render_authorized") is True:
        raise ValueError("Preview composer accepts draft timelines only.")
    if timeline.get("publishing_authorized") is True:
        raise ValueError("Preview composer does not accept publishing-authorized timelines.")
    rows = timeline.get("scenes")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Timeline must contain at least one scene.")
    clean = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("Malformed scene record.")
        duration = _finite(row.get("duration_seconds", 0), "Scene duration")
        if not MIN_DURATION <= duration <= MAX_DURATION:
            raise ValueError(f"Scene {index + 1} duration is outside supported bounds.")
        transition = str(row.get("transition_in", "cut")).lower()
        transition_duration = _finite(row.get("transition_duration_seconds", 0), "Transition duration")
        if transition != "cut" or transition_duration != 0:
            raise ValueError("Preview composer currently supports cuts only; transition effects are not rendered.")
        media = Path(str(row.get("visual_path") or "")).expanduser()
        if not media.is_file() or media.is_symlink():
            raise ValueError(f"Scene {index + 1} requires a valid local non-symlink media file.")
        clean.append(dict(row, duration_seconds=duration, visual_path=str(media.resolve())))
    return clean


def compose_preview(
    timeline: dict[str, Any],
    output_path: Path,
    *,
    ffmpeg: str | None = None,
    timeout: int = 900,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    runner: Callable[..., Any] = subprocess.run,
) -> Path:
    """Compose a local MP4 preview from images/videos using cuts and optional subtitles.

    Inputs must be local files. Output must be a new path. No network inputs are accepted.
    """
    if timeout < 1 or width < 2 or height < 2 or fps < 1:
        raise ValueError("Invalid preview output settings.")
    scenes = _validate_timeline(timeline)
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("FFmpeg executable not found; install FFmpeg and add it to PATH.")
    destination = output_path.expanduser().resolve()
    if destination.exists():
        raise ValueError("Preview output already exists; choose a new file to avoid overwriting.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="money-geta-preview-", dir=str(destination.parent)) as temp_name:
        temp = Path(temp_name)
        segments: list[Path] = []
        for index, scene in enumerate(scenes, start=1):
            source = Path(scene["visual_path"])
            segment = temp / f"segment_{index:04d}.mp4"
            duration = scene["duration_seconds"]
            start = _finite(scene.get("media_trim_start_seconds", 0), "Trim start")
            end_raw = scene.get("media_trim_end_seconds")
            end = None if end_raw is None else _finite(end_raw, "Trim end")
            if start < 0 or (end is not None and end <= start):
                raise ValueError(f"Scene {index} has invalid video trim values.")
            suffix = source.suffix.lower()
            is_image = suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
            if is_image and (start != 0 or end is not None):
                raise ValueError(f"Scene {index}: trim settings apply to video only.")
            if not is_image and end is not None and end - start < duration:
                duration = end - start
            args = [executable, "-hide_banner", "-loglevel", "error", "-y"]
            if is_image:
                args += ["-loop", "1", "-framerate", str(fps), "-i", str(source)]
            else:
                args += ["-ss", str(start), "-i", str(source)]
            args += ["-t", f"{duration:.3f}", "-an", "-vf",
                     f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                     f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p"]
            text = _subtitle_text(scene.get("subtitle_text", ""))
            subtitle_start = _finite(scene.get("subtitle_start_seconds", 0), "Subtitle start")
            subtitle_end_raw = scene.get("subtitle_end_seconds")
            subtitle_end = duration if subtitle_end_raw is None else _finite(subtitle_end_raw, "Subtitle end")
            if text and subtitle_end > subtitle_start and subtitle_start >= 0 and subtitle_end <= duration:
                srt = temp / f"subtitle_{index:04d}.srt"
                srt.write_text(f"1\\n00:00:{subtitle_start:06.3f} --> 00:00:{subtitle_end:06.3f}\\n{text}\\n", encoding="utf-8")
                args[-2] += f",subtitles='{_filter_path(srt)}':force_style='FontSize=28,Outline=2,Shadow=1,Alignment=2,MarginV=90'"
            args += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-movflags", "+faststart", str(segment)]
            result = runner(args, capture_output=True, text=True, timeout=timeout, check=False)
            if getattr(result, "returncode", 0) != 0:
                raise RuntimeError(f"FFmpeg preview segment {index} failed: {(getattr(result, 'stderr', '') or '')[-1000:]}")
            if not segment.is_file():
                # Test runners may not write a file; production FFmpeg must.
                if runner is subprocess.run:
                    raise RuntimeError(f"FFmpeg did not create preview segment {index}.")
            segments.append(segment)
        manifest = temp / "concat.txt"
        manifest.write_text("".join(f"file '{_filter_path(path)}'\\n" for path in segments), encoding="utf-8")
        concat_args = [executable, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                       "-i", str(manifest), "-c", "copy", "-movflags", "+faststart", str(destination)]
        final = runner(concat_args, capture_output=True, text=True, timeout=timeout, check=False)
        if getattr(final, "returncode", 0) != 0:
            raise RuntimeError(f"FFmpeg preview assembly failed: {(getattr(final, 'stderr', '') or '')[-1000:]}")
        if runner is subprocess.run and (not destination.is_file() or destination.stat().st_size == 0):
            raise RuntimeError("FFmpeg did not produce a non-empty preview.")
    return destination
