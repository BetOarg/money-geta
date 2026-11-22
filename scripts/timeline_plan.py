"""Editable local timeline drafts derived from a reviewed scene visual plan."""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from pathlib import Path
from typing import Any

from scripts.project_registry import default_projects_root

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
_SHA = re.compile(r"^[a-fA-F0-9]{64}$")
MIN_DURATION = 0.25
MAX_DURATION = 180.0


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"Invalid {label}.")
    return value


def create_timeline_from_visual_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Convert visual scenes into editable timeline rows without authorizing render."""
    if not isinstance(plan, dict) or plan.get("plan_type") != "scene_asset_suggestions":
        raise ValueError("A scene-asset visual plan is required.")
    project_id = _identifier(plan.get("project_id"), "project ID")
    campaign_id = _identifier(plan.get("campaign_id"), "campaign ID")
    script_id = _identifier(plan.get("script_id"), "script ID")
    script_sha = plan.get("script_sha256")
    if not isinstance(script_sha, str) or not _SHA.fullmatch(script_sha):
        raise ValueError("A valid script SHA-256 is required.")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("The visual plan must contain at least one scene.")
    rows = []
    for position, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError("Malformed scene record.")
        selected = scene.get("selected_candidate_id") or ""
        asset = scene.get("selected_asset") or {}
        if selected:
            suggestions = scene.get("suggestions", [])
            allowed = {item.get("candidate_id") for item in suggestions if isinstance(item, dict)}
            if selected not in allowed or asset.get("candidate_id") != selected:
                raise ValueError("Selected asset metadata must match a scene suggestion.")
            if (asset.get("rights_status") != "reviewed_approved"
                    or asset.get("integrity_status") != "verified"
                    or asset.get("metadata_current") is not True):
                raise ValueError("Timeline assets must have current approved rights and verified integrity.")
        narration = str(scene.get("narration") or "").strip()
        rows.append({
            "scene_id": f"scene-{position:03d}",
            "source_scene_index": int(scene.get("scene_index", position)),
            "position": position,
            "duration_seconds": 5.0,
            "visual_path": str(asset.get("local_path") or "") if selected else "",
            "candidate_id": selected,
            "visual_description": str(scene.get("visual") or "").strip(),
            "narration": narration,
            "subtitle_text": narration,
        })
    return {
        "schema_version": 1,
        "plan_type": "editable_timeline",
        "project_id": project_id,
        "campaign_id": campaign_id,
        "script_id": script_id,
        "script_sha256": script_sha,
        "status": "draft",
        "scenes": rows,
        "human_review_required": True,
        "render_authorized": False,
        "publishing_authorized": False,
        "audio_tracks": [],
    }


def move_scene(timeline: dict[str, Any], scene_index: int, offset: int) -> dict[str, Any]:
    """Move one scene up/down and normalize positions. Returns a copy."""
    rows = list(timeline.get("scenes", []))
    if not 0 <= scene_index < len(rows) or offset not in (-1, 1):
        raise ValueError("Invalid scene move.")
    target = scene_index + offset
    if not 0 <= target < len(rows):
        return dict(timeline)
    rows[scene_index], rows[target] = rows[target], rows[scene_index]
    for position, row in enumerate(rows, start=1):
        row = dict(row)
        row["position"] = position
        rows[position - 1] = row
    result = dict(timeline)
    result["scenes"] = rows
    return result


TRANSITIONS = {"cut", "fade", "dissolve", "slide"}


def update_scene_transition(timeline: dict[str, Any], scene_index: int, *, transition: str, duration_seconds: float) -> dict[str, Any]:
    rows = list(timeline.get("scenes", []))
    if not 0 <= scene_index < len(rows):
        raise ValueError("Scene index out of range.")
    kind = str(transition).strip().lower()
    duration = float(duration_seconds)
    scene_duration = float(rows[scene_index].get("duration_seconds", 0))
    if kind not in TRANSITIONS:
        raise ValueError("Unsupported transition type.")
    if not math.isfinite(duration) or duration < 0:
        raise ValueError("Transition duration must be finite and non-negative.")
    if kind == "cut" and duration != 0:
        raise ValueError("Cut transition duration must be zero.")
    if kind != "cut" and (duration <= 0 or duration > scene_duration):
        raise ValueError("Transition duration must be positive and fit inside the scene.")
    row = dict(rows[scene_index])
    row["transition_in"] = kind
    row["transition_duration_seconds"] = round(duration, 3)
    rows[scene_index] = row
    result = dict(timeline)
    result["scenes"] = rows
    return result


def update_subtitle_timing(timeline: dict[str, Any], scene_index: int, *, start_seconds: float, end_seconds: float) -> dict[str, Any]:
    rows = list(timeline.get("scenes", []))
    if not 0 <= scene_index < len(rows):
        raise ValueError("Scene index out of range.")
    row = dict(rows[scene_index])
    start = float(start_seconds)
    end = float(end_seconds)
    duration = float(row.get("duration_seconds", 0))
    if not all(math.isfinite(value) for value in (start, end)):
        raise ValueError("Subtitle timing must be finite.")
    if start < 0 or end <= start or end > duration:
        raise ValueError("Subtitle timing must fit inside the scene duration.")
    row["subtitle_start_seconds"] = round(start, 3)
    row["subtitle_end_seconds"] = round(end, 3)
    rows[scene_index] = row
    result = dict(timeline)
    result["scenes"] = rows
    return result


def update_scene(timeline: dict[str, Any], scene_index: int, *, duration_seconds: float | None = None,
                narration: str | None = None, subtitle_text: str | None = None,
                trim_start_seconds: float | None = None, trim_end_seconds: float | None = None) -> dict[str, Any]:
    rows = list(timeline.get("scenes", []))
    if not 0 <= scene_index < len(rows):
        raise ValueError("Scene index out of range.")
    row = dict(rows[scene_index])
    if duration_seconds is not None:
        duration = float(duration_seconds)
        if not MIN_DURATION <= duration <= MAX_DURATION:
            raise ValueError(f"Duration must be between {MIN_DURATION} and {MAX_DURATION} seconds.")
        row["duration_seconds"] = round(duration, 3)
    if narration is not None:
        row["narration"] = str(narration)
    if subtitle_text is not None:
        row["subtitle_text"] = str(subtitle_text)
    if trim_start_seconds is not None or trim_end_seconds is not None:
        start_seconds = float(trim_start_seconds or 0)
        end_seconds = None if trim_end_seconds in (None, "") else float(trim_end_seconds)
        if not math.isfinite(start_seconds) or start_seconds < 0:
            raise ValueError("Media trim start must be a finite non-negative number.")
        if end_seconds is not None and (not math.isfinite(end_seconds) or end_seconds <= start_seconds):
            raise ValueError("Media trim end must be finite and greater than start.")
        if start_seconds > 0 or end_seconds is not None:
            from scripts.timeline_preview import resolve_scene_preview_path
            _, kind = resolve_scene_preview_path(row.get("visual_path", ""))
            if kind != "video":
                raise ValueError("Trim controls are only available for local video assets.")
            row["media_trim_start_seconds"] = round(start_seconds, 3)
            if end_seconds is None:
                row.pop("media_trim_end_seconds", None)
            else:
                row["media_trim_end_seconds"] = round(end_seconds, 3)
        else:
            row.pop("media_trim_start_seconds", None)
            row.pop("media_trim_end_seconds", None)
    rows[scene_index] = row
    result = dict(timeline)
    result["scenes"] = rows
    return result


def save_timeline(timeline: dict[str, Any], *, root: Path | None = None) -> Path:
    """Persist timeline draft atomically inside its project campaign directory."""
    if not isinstance(timeline, dict) or timeline.get("plan_type") != "editable_timeline":
        raise ValueError("Only editable timeline drafts can be saved.")
    project_id = _identifier(timeline.get("project_id"), "project ID")
    campaign_id = _identifier(timeline.get("campaign_id"), "campaign ID")
    script_id = _identifier(timeline.get("script_id"), "script ID")
    sha = timeline.get("script_sha256")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise ValueError("A valid script SHA-256 is required.")
    rows = timeline.get("scenes")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Timeline must contain scenes.")
    audio_rows = timeline.get("audio_tracks", [])
    if not isinstance(audio_rows, list):
        raise ValueError("Audio tracks must be a list.")
    from scripts.timeline_audio import validate_audio_track
    normalized_audio = [validate_audio_track(item) for item in audio_rows]
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed timeline scene record.")
        scene_id = row.get("scene_id")
        if not isinstance(scene_id, str) or not _ID.fullmatch(scene_id) or scene_id in seen:
            raise ValueError("Scene IDs must be unique and valid.")
        seen.add(scene_id)
        duration = float(row.get("duration_seconds", 0))
        if not MIN_DURATION <= duration <= MAX_DURATION:
            raise ValueError(f"Duration must be between {MIN_DURATION} and {MAX_DURATION} seconds.")
        trim_start = float(row.get("media_trim_start_seconds", 0))
        trim_end_raw = row.get("media_trim_end_seconds")
        trim_end = None if trim_end_raw is None else float(trim_end_raw)
        if not math.isfinite(trim_start) or trim_start < 0:
            raise ValueError("Media trim start must be finite and non-negative.")
        if trim_end is not None and (not math.isfinite(trim_end) or trim_end <= trim_start):
            raise ValueError("Media trim end must be finite and greater than start.")
        if trim_start > 0 or trim_end is not None:
            from scripts.timeline_preview import resolve_scene_preview_path
            _, kind = resolve_scene_preview_path(row.get("visual_path", ""))
            if kind != "video":
                raise ValueError("Media trim controls require a local video asset.")
        transition = str(row.get("transition_in", "cut")).lower()
        transition_duration = float(row.get("transition_duration_seconds", 0))
        if transition not in TRANSITIONS or not math.isfinite(transition_duration) or transition_duration < 0:
            raise ValueError("Invalid transition metadata.")
        if transition == "cut" and transition_duration != 0:
            raise ValueError("Cut transition duration must be zero.")
        if transition != "cut" and (transition_duration <= 0 or transition_duration > duration):
            raise ValueError("Transition duration must be positive and fit inside the scene.")
        subtitle_start = float(row.get("subtitle_start_seconds", 0))
        subtitle_end_raw = row.get("subtitle_end_seconds")
        subtitle_end = None if subtitle_end_raw is None else float(subtitle_end_raw)
        if not math.isfinite(subtitle_start) or subtitle_start < 0:
            raise ValueError("Subtitle start must be finite and non-negative.")
        if subtitle_end is not None and (not math.isfinite(subtitle_end) or subtitle_end <= subtitle_start or subtitle_end > duration):
            raise ValueError("Subtitle timing must fit inside the scene duration.")
        if subtitle_end is not None and not str(row.get("subtitle_text", "")).strip():
            raise ValueError("Subtitle timing requires subtitle text.")
        for field in ("narration", "subtitle_text", "visual_description", "visual_path", "candidate_id"):
            if not isinstance(row.get(field, ""), str):
                raise ValueError(f"{field} must be text.")
    projects_root = (root or default_projects_root()).expanduser().resolve()
    campaign_dir = projects_root / project_id / "campaigns" / campaign_id
    from scripts.artifact_registry import _reject_symlink_components
    _reject_symlink_components(campaign_dir)
    if not campaign_dir.is_dir():
        raise ValueError("Campaign folder does not exist.")
    timeline_dir = campaign_dir / "timelines"
    timeline_dir.mkdir(exist_ok=True)
    _reject_symlink_components(timeline_dir)
    resolved_campaign = campaign_dir.resolve(strict=True)
    resolved_dir = timeline_dir.resolve(strict=True)
    if not resolved_dir.is_relative_to(resolved_campaign):
        raise ValueError("Timeline path escapes campaign folder.")
    target = timeline_dir / f"timeline_{script_id}_{sha[:12]}.json"
    if target.is_symlink():
        raise ValueError("Timeline target cannot be a symlink.")
    temp = timeline_dir / f".tmp-{uuid.uuid4().hex}"
    payload = dict(timeline)
    payload["audio_tracks"] = normalized_audio
    payload["status"] = "draft"
    payload["human_review_required"] = True
    payload["render_authorized"] = False
    payload["publishing_authorized"] = False
    try:
        with temp.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    return target


def load_timeline(project_id: str, campaign_id: str, script_id: str, sha: str, *, root: Path | None = None) -> dict[str, Any] | None:
    """Load a saved timeline for the exact script ID and SHA; return None if absent."""
    project_id = _identifier(project_id, "project ID")
    campaign_id = _identifier(campaign_id, "campaign ID")
    script_id = _identifier(script_id, "script ID")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise ValueError("A valid script SHA-256 is required.")
    campaign_dir = (root or default_projects_root()).expanduser().resolve() / project_id / "campaigns" / campaign_id
    from scripts.artifact_registry import _reject_symlink_components
    _reject_symlink_components(campaign_dir)
    if not campaign_dir.is_dir():
        return None
    target = campaign_dir / "timelines" / f"timeline_{script_id}_{sha[:12]}.json"
    _reject_symlink_components(target)
    if not target.is_file():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("plan_type") != "editable_timeline" or payload.get("script_sha256") != sha:
        raise ValueError("Saved timeline does not match the approved script hash.")
    audio_rows = payload.get("audio_tracks", [])
    if not isinstance(audio_rows, list):
        raise ValueError("Saved audio tracks must be a list.")
    from scripts.timeline_audio import validate_audio_track
    payload["audio_tracks"] = [validate_audio_track(row) for row in audio_rows]
    return payload


def timeline_visual_blocks(scenes: list[dict[str, Any]], *, pixels_per_second: float = 24.0, minimum_width: float = 40.0, gap: float = 6.0) -> list[dict[str, float | int]]:
    """Calculate proportional scene block positions for a scrollable visual timeline."""
    if not isinstance(scenes, list) or not scenes:
        return []
    scale = float(pixels_per_second)
    min_width = float(minimum_width)
    spacing = float(gap)
    if not (0.1 <= scale <= 200 and 10 <= min_width <= 500 and 0 <= spacing <= 50):
        raise ValueError("Invalid timeline display dimensions.")
    blocks = []
    x = 12.0
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError("Malformed scene record.")
        duration = float(scene.get("duration_seconds", 0))
        if not MIN_DURATION <= duration <= MAX_DURATION:
            raise ValueError("Scene duration out of range.")
        width = max(min_width, duration * scale)
        blocks.append({"index": index, "x": x, "width": width, "duration": duration})
        x += width + spacing
    return blocks
