"""Deterministic, approval-gated matching of script scenes to local media."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from scripts.media_library import list_media_assets
from scripts.project_registry import default_projects_root
from scripts.script_registry import check_script, list_scripts

STOP_WORDS = frozenset("""
a al algo algun alguna algunos antes aqui asi aunque bajo cada casi como con contra cual cuando cuanto de del desde donde dos el ella ellas ellos en entre era es esa ese eso esta estas este estos fue ha hacia hay la las le les lo los mas menos mi mis muy no nos o os para pero por porque que quien se sin sobre su sus te tu tus un una unas uno unos y ya yo me mi
the a an and are as at be been being by for from in into is it its of on or that this to with we you your he she they them their his her has have had not no so but about up down
""".split())


def tokenize(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return {word for word in re.findall(r"[a-z0-9]+", normalized) if len(word) >= 3 and word not in STOP_WORDS}


def _asset_text(asset: dict[str, Any]) -> str:
    return " ".join(str(asset.get(key) or "") for key in (
        "title", "creator", "attribution", "license", "source_page_url", "candidate_id"
    ))


def match_scene(scene: dict[str, Any], assets: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    visual_terms = tokenize(scene.get("visual", ""))
    narration_terms = tokenize(scene.get("narration", ""))
    scene_terms = visual_terms | narration_terms
    if not scene_terms:
        return []
    scored = []
    for asset in assets:
        if not asset.get("usable_for_selection"):
            continue
        asset_terms = tokenize(_asset_text(asset))
        matched_visual = sorted(visual_terms & asset_terms)
        matched_context = sorted((narration_terms - visual_terms) & asset_terms)
        # Visual matches carry more weight than narration-only context.
        score = (2 * len(matched_visual) + len(matched_context)) / (2 * max(len(visual_terms), 1) + max(len(narration_terms - visual_terms), 1))
        if not matched_visual and not matched_context:
            continue
        scored.append({
            "candidate_id": asset.get("candidate_id"),
            "title": asset.get("title", ""),
            "creator": asset.get("creator", ""),
            "local_path": asset.get("local_path", ""),
            "file_sha256": asset.get("file_sha256", ""),
            "license": asset.get("license", ""),
            "rights_status": asset.get("rights_status", ""),
            "integrity_status": asset.get("integrity_status", ""),
            "metadata_current": asset.get("metadata_current", False),
            "score": round(score, 4),
            "matched_visual_terms": matched_visual,
            "matched_context_terms": matched_context,
            "rationale": "Coincidencias visuales: " + ", ".join(matched_visual) if matched_visual else "Solo coincidencias contextuales: " + ", ".join(matched_context),
        })
    return sorted(scored, key=lambda item: (-item["score"], item["candidate_id"] or ""))[:max(1, min(int(limit), 10))]


def build_scene_asset_plan(project_id: str, campaign_id: str, script_id: str, sha256: str, *,
                          root: Path | None = None, limit_per_scene: int = 5) -> dict[str, Any]:
    """Create a suggestions-only plan for a currently approved, hash-verified script."""
    projects_root = (root or default_projects_root()).expanduser().resolve()
    registrations = list_scripts(project_id, campaign_id, root=projects_root)
    registration = next((row for row in registrations if row.get("script_id") == script_id), None)
    if not registration or registration.get("sha256") != sha256:
        raise ValueError("Script registration/hash was not found for this campaign.")
    passed, problems = check_script(project_id, campaign_id, script_id, sha256, root=projects_root)
    if not passed:
        raise ValueError("Scene matching requires a currently approved script: " + "; ".join(problems))
    from scripts.artifact_registry import _reject_symlink_components
    script_path = Path(registration.get("path", "")).expanduser()
    _reject_symlink_components(script_path)
    resolved_script = script_path.resolve(strict=True)
    campaign_drafts = (projects_root / project_id / "campaigns" / campaign_id / "drafts").resolve(strict=False)
    if not resolved_script.is_file() or not resolved_script.is_relative_to(campaign_drafts):
        raise ValueError("Approved script path must remain inside the campaign drafts directory.")
    import json
    payload = json.loads(resolved_script.read_text(encoding="utf-8"))
    scenes = payload.get("script", {}).get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Approved script has no valid scenes.")
    assets = list_media_assets(project_id=project_id, campaign_id=campaign_id, root=projects_root)
    approved_assets = [asset for asset in assets if asset.get("usable_for_selection") is True]
    scene_rows = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError("Script scene record is malformed.")
        scene_rows.append({
            "scene_index": index,
            "visual": scene.get("visual", ""),
            "narration": scene.get("narration", ""),
            "suggestions": match_scene(scene, approved_assets, limit=limit_per_scene),
        })
    return {
        "schema_version": 1,
        "plan_type": "scene_asset_suggestions",
        "project_id": project_id,
        "campaign_id": campaign_id,
        "script_id": script_id,
        "script_sha256": sha256,
        "status": "suggestions_only",
        "asset_pool_count": len(approved_assets),
        "scene_count": len(scene_rows),
        "scenes": scene_rows,
        "human_review_required": True,
        "render_authorized": False,
        "publishing_authorized": False,
    }
