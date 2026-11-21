"""Persistence helpers for human-reviewed scene visual plans."""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from scripts.project_registry import default_projects_root

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
_SHA = re.compile(r"^[a-fA-F0-9]{64}$")


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"Invalid {label}.")
    return value


def save_scene_visual_plan(plan: dict[str, Any], *, root: Path | None = None) -> Path:
    """Atomically save scene selections without authorizing rendering or publishing."""
    if not isinstance(plan, dict) or plan.get("plan_type") != "scene_asset_suggestions":
        raise ValueError("Only a scene-asset suggestion plan can be saved.")
    project_id = _identifier(plan.get("project_id"), "project ID")
    campaign_id = _identifier(plan.get("campaign_id"), "campaign ID")
    script_id = _identifier(plan.get("script_id"), "script ID")
    sha = plan.get("script_sha256")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise ValueError("A valid script SHA-256 is required.")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("The plan must contain scenes.")
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("Malformed scene record.")
        suggestions = scene.get("suggestions", [])
        if not isinstance(suggestions, list):
            raise ValueError("Scene suggestions must be a list.")
        valid_ids = {item.get("candidate_id") for item in suggestions if isinstance(item, dict)}
        selected = scene.get("selected_candidate_id")
        if selected and selected not in valid_ids:
            raise ValueError("Selected asset must belong to the scene's suggestions.")
        selected_asset = scene.get("selected_asset")
        if selected and (not isinstance(selected_asset, dict) or selected_asset.get("candidate_id") != selected):
            raise ValueError("Selected asset metadata must match the selected candidate ID.")
        if not selected and selected_asset is not None:
            raise ValueError("Selected asset metadata cannot exist without a candidate ID.")
        if not isinstance(scene.get("human_reviewed", False), bool):
            raise ValueError("Scene review status must be boolean.")

    projects_root = (root or default_projects_root()).expanduser().resolve()
    project_dir = projects_root / project_id
    campaign_dir = project_dir / "campaigns" / campaign_id
    from scripts.artifact_registry import _reject_symlink_components
    _reject_symlink_components(campaign_dir)
    if not campaign_dir.is_dir():
        raise ValueError("Campaign folder does not exist.")
    plan_dir = campaign_dir / "visual_plans"
    plan_dir.mkdir(exist_ok=True)
    _reject_symlink_components(plan_dir)
    resolved_campaign = campaign_dir.resolve(strict=True)
    resolved_plan_dir = plan_dir.resolve(strict=True)
    if not resolved_plan_dir.is_relative_to(resolved_campaign):
        raise ValueError("Visual plan path escapes campaign folder.")
    target = plan_dir / f"scene_asset_plan_{script_id}_{sha[:12]}.json"
    if target.is_symlink():
        raise ValueError("Plan target cannot be a symlink.")
    temp = plan_dir / f".tmp-{uuid.uuid4().hex}"
    payload = dict(plan)
    payload["status"] = "reviewed" if all(s.get("human_reviewed") for s in scenes) else "review_pending"
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
