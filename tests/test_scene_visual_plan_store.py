import json
from pathlib import Path

import pytest

from scripts.scene_visual_plan_store import save_scene_visual_plan


def sample_plan():
    return {
        "plan_type": "scene_asset_suggestions",
        "project_id": "project-1",
        "campaign_id": "campaign-1",
        "script_id": "script-1",
        "script_sha256": "a" * 64,
        "scenes": [{
            "scene_index": 1,
            "visual": "City skyline",
            "narration": "Opening",
            "suggestions": [{"candidate_id": "asset-1", "title": "Skyline", "usable_for_selection": True}],
            "selected_candidate_id": "asset-1",
            "human_reviewed": True,
        }],
    }


def test_save_scene_visual_plan_persists_review_and_keeps_render_blocked(tmp_path):
    campaign = tmp_path / "project-1" / "campaigns" / "campaign-1"
    campaign.mkdir(parents=True)
    path = save_scene_visual_plan(sample_plan(), root=tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.parent == campaign / "visual_plans"
    assert saved["status"] == "reviewed"
    assert saved["human_review_required"] is True
    assert saved["render_authorized"] is False
    assert saved["publishing_authorized"] is False


def test_save_scene_visual_plan_rejects_asset_not_in_scene_suggestions(tmp_path):
    campaign = tmp_path / "project-1" / "campaigns" / "campaign-1"
    campaign.mkdir(parents=True)
    plan = sample_plan()
    plan["scenes"][0]["selected_candidate_id"] = "not-suggested"
    with pytest.raises(ValueError, match="belong to the scene"):
        save_scene_visual_plan(plan, root=tmp_path)


def test_save_scene_visual_plan_rejects_path_traversal(tmp_path):
    campaign = tmp_path / "project-1" / "campaigns" / "campaign-1"
    campaign.mkdir(parents=True)
    plan = sample_plan()
    plan["project_id"] = "../outside"
    with pytest.raises(ValueError, match="Invalid project ID"):
        save_scene_visual_plan(plan, root=tmp_path)

def test_scene_visual_plan_selection_metadata_must_match_candidate_id(tmp_path):
    campaign = tmp_path / "project-1" / "campaigns" / "campaign-1"
    campaign.mkdir(parents=True)
    plan = sample_plan()
    plan["scenes"][0]["selected_asset"]["candidate_id"] = "mismatch"
    with pytest.raises(ValueError, match="metadata must match"):
        save_scene_visual_plan(plan, root=tmp_path)
