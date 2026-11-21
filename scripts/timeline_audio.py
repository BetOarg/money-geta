"""Draft audio tracks for Money-Geta timelines; local-only metadata."""
from __future__ import annotations

from pathlib import Path
import math

SUPPORTED_AUDIO = {".wav", ".mp3", ".ogg", ".m4a", ".aac", ".flac"}


def validate_audio_track(track: dict, *, project_root: Path | None = None) -> dict:
    """Validate audio draft metadata and resolve an optional local source."""
    if not isinstance(track, dict):
        raise ValueError("Audio track must be an object.")
    name = str(track.get("name", "")).strip()
    if not name:
        raise ValueError("Audio track name is required.")
    source_raw = str(track.get("source_path", "")).strip()
    source = None
    if source_raw:
        p = Path(source_raw).expanduser()
        try:
            if p.is_symlink():
                raise ValueError("Audio source symlinks are not allowed.")
            source = p.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError("Audio source file is missing or inaccessible.") from exc
        if not source.is_file() or source.suffix.lower() not in SUPPORTED_AUDIO:
            raise ValueError("Audio source must be a supported local audio file.")
        if project_root is not None:
            root = Path(project_root).resolve()
            try:
                source.relative_to(root)
            except ValueError as exc:
                raise ValueError("Audio source must be inside the project folder.") from exc
    start = float(track.get("start_seconds", 0))
    duration = float(track.get("duration_seconds", 0))
    volume = float(track.get("volume", 1.0))
    fade_in = float(track.get("fade_in_seconds", 0))
    fade_out = float(track.get("fade_out_seconds", 0))
    for label, value in (("start", start), ("duration", duration), ("volume", volume),
                          ("fade in", fade_in), ("fade out", fade_out)):
        if not math.isfinite(value):
            raise ValueError(f"Audio {label} must be finite.")
    if start < 0 or duration <= 0 or not 0 <= volume <= 2 or fade_in < 0 or fade_out < 0:
        raise ValueError("Audio timing, fades, or volume are out of range.")
    if fade_in + fade_out > duration:
        raise ValueError("Audio fades cannot exceed the track duration.")
    return {
        "name": name, "source_path": str(source) if source else "",
        "start_seconds": round(start, 3), "duration_seconds": round(duration, 3),
        "volume": round(volume, 3), "fade_in_seconds": round(fade_in, 3),
        "fade_out_seconds": round(fade_out, 3),
    }


def update_audio_track(timeline: dict, index: int, track: dict, *, project_root: Path | None = None) -> dict:
    rows = list(timeline.get("audio_tracks", []))
    if not 0 <= index <= len(rows):
        raise ValueError("Audio track index out of range.")
    normalized = validate_audio_track(track, project_root=project_root)
    if index == len(rows):
        rows.append(normalized)
    else:
        rows[index] = normalized
    result = dict(timeline)
    result["audio_tracks"] = rows
    return result


def remove_audio_track(timeline: dict, index: int) -> dict:
    rows = list(timeline.get("audio_tracks", []))
    if not 0 <= index < len(rows):
        raise ValueError("Audio track index out of range.")
    rows.pop(index)
    result = dict(timeline)
    result["audio_tracks"] = rows
    return result
