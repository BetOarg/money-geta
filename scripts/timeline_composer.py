"""Local FFmpeg preview composer for editable timeline drafts."""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from scripts.timeline_plan import MIN_DURATION, MAX_DURATION


def _finite(value: Any, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite.")
    return number


def _filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def _clean_subtitle(value: Any) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32).strip()


def _srt_timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def _validate(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(timeline, dict) or timeline.get("plan_type") != "editable_timeline":
        raise ValueError("An editable timeline draft is required.")
    if timeline.get("render_authorized") is True or timeline.get("publishing_authorized") is True:
        raise ValueError("Preview composer accepts draft timelines only.")
    scenes = timeline.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Timeline must contain at least one scene.")
    validated = []
    for idx, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise ValueError("Malformed scene record.")
        duration = _finite(scene.get("duration_seconds", 0), "Scene duration")
        if not MIN_DURATION <= duration <= MAX_DURATION:
            raise ValueError(f"Scene {idx} duration is outside supported bounds.")
        transition = str(scene.get("transition_in", "cut")).lower()
        transition_duration = _finite(scene.get("transition_duration_seconds", 0), "Transition duration")
        if transition != "cut" or transition_duration != 0:
            raise ValueError("Preview composer currently supports cuts only; transition effects are not rendered.")
        media = Path(str(scene.get("visual_path") or "")).expanduser()
        if not media.is_file() or media.is_symlink():
            raise ValueError(f"Scene {idx} requires a valid local non-symlink media file.")
        validated.append(dict(scene, duration_seconds=duration, visual_path=str(media.resolve())))
    return validated


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
    """Render a local, draft-only preview MP4. No final-render or publish gate is changed."""
    if timeout < 1 or width < 2 or height < 2 or fps < 1:
        raise ValueError("Invalid preview output settings.")
    scenes = _validate(timeline)
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("FFmpeg executable not found; install FFmpeg and add it to PATH.")
    destination = output_path.expanduser().resolve()
    if destination.exists():
        raise ValueError("Preview output already exists; choose a new file to avoid overwriting.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="money-geta-preview-", dir=str(destination.parent)) as work:
        temp = Path(work)
        segments = []
        for index, scene in enumerate(scenes, 1):
            source = Path(scene["visual_path"])
            segment = temp / f"segment_{index:04d}.mp4"
            duration = scene["duration_seconds"]
            trim_start = _finite(scene.get("media_trim_start_seconds", 0), "Trim start")
            trim_end_raw = scene.get("media_trim_end_seconds")
            trim_end = None if trim_end_raw is None else _finite(trim_end_raw, "Trim end")
            if trim_start < 0 or (trim_end is not None and trim_end <= trim_start):
                raise ValueError(f"Scene {index} has invalid video trim values.")
            image = source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
            if image and (trim_start != 0 or trim_end is not None):
                raise ValueError(f"Scene {index}: trim settings apply to video only.")
            source_duration = None if trim_end is None else trim_end - trim_start
            args = [executable, "-hide_banner", "-loglevel", "error", "-y"]
            if image:
                args += ["-loop", "1", "-framerate", str(fps), "-i", str(source)]
            else:
                args += ["-ss", str(trim_start), "-i", str(source)]
            args += ["-t", f"{duration:.3f}", "-an", "-vf"]
            filters = []
            if source_duration is not None:
                filters.extend([f"trim=duration={source_duration:.3f}", "setpts=PTS-STARTPTS"])
                padding = max(0.0, duration - source_duration)
                if padding:
                    filters.append(f"tpad=stop_mode=clone:stop_duration={padding:.3f}")
            filters.extend([
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                "setsar=1", f"fps={fps}", "format=yuv420p",
            ])
            subtitle = _clean_subtitle(scene.get("subtitle_text", ""))
            sub_start = _finite(scene.get("subtitle_start_seconds", 0), "Subtitle start")
            sub_end_raw = scene.get("subtitle_end_seconds")
            sub_end = duration if sub_end_raw is None else _finite(sub_end_raw, "Subtitle end")
            if subtitle and 0 <= sub_start < sub_end <= duration:
                srt_path = temp / f"subtitle_{index:04d}.srt"
                srt_path.write_text(
                    "1\n" + _srt_timestamp(sub_start) + " --> " + _srt_timestamp(sub_end) + "\n" + subtitle + "\n",
                    encoding="utf-8",
                )
                filters.append(
                    f"subtitles='{_filter_path(srt_path)}':force_style='FontSize=28,Outline=2,Shadow=1,Alignment=2,MarginV=90'"
                )
            args.append(",".join(filters))
            args += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-movflags", "+faststart", str(segment)]
            result = runner(args, capture_output=True, text=True, timeout=timeout, check=False)
            if getattr(result, "returncode", 0) != 0:
                raise RuntimeError(f"FFmpeg preview segment {index} failed: {(getattr(result, 'stderr', '') or '')[-1000:]}")
            if runner is subprocess.run and not segment.is_file():
                raise RuntimeError(f"FFmpeg did not create preview segment {index}.")
            segments.append(segment)
        manifest = temp / "concat.txt"
        manifest.write_text("".join("file '" + _filter_path(path) + "'\n" for path in segments), encoding="utf-8")
        concat_args = [
            executable, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(manifest), "-c", "copy", "-movflags", "+faststart", str(destination),
        ]
        final = runner(concat_args, capture_output=True, text=True, timeout=timeout, check=False)
        if getattr(final, "returncode", 0) != 0:
            raise RuntimeError(f"FFmpeg preview assembly failed: {(getattr(final, 'stderr', '') or '')[-1000:]}")
        if runner is subprocess.run and (not destination.is_file() or destination.stat().st_size == 0):
            raise RuntimeError("FFmpeg did not produce a non-empty preview.")
    return destination
