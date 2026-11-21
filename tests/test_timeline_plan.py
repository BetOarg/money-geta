import json

import pytest

from scripts.timeline_plan import (
    create_timeline_from_visual_plan, move_scene, update_scene, save_timeline, load_timeline, timeline_visual_blocks,
)


def plan():
    return {
        "plan_type": "scene_asset_suggestions",
        "project_id": "proj-1",
        "campaign_id": "campaign-1",
        "script_id": "script-1",
        "script_sha256": "a" * 64,
        "scenes": [
            {"scene_index": 1, "visual": "Opening street", "narration": "Welcome",
             "suggestions": [], "selected_candidate_id": "", "selected_asset": None},
            {"scene_index": 2, "visual": "Close-up", "narration": "Details",
             "suggestions": [], "selected_candidate_id": "", "selected_asset": None},
        ],
    }


def test_create_timeline_defaults_and_render_blocked():
    timeline = create_timeline_from_visual_plan(plan())
    assert len(timeline["scenes"]) == 2
    assert timeline["scenes"][0]["duration_seconds"] == 5.0
    assert timeline["scenes"][0]["subtitle_text"] == "Welcome"
    assert timeline["render_authorized"] is False
    assert timeline["publishing_authorized"] is False


def test_move_scene_swaps_and_normalizes_positions():
    timeline = create_timeline_from_visual_plan(plan())
    moved = move_scene(timeline, 0, 1)
    assert moved["scenes"][0]["visual_description"] == "Close-up"
    assert moved["scenes"][0]["position"] == 1
    assert moved["scenes"][1]["position"] == 2
    assert timeline["scenes"][0]["visual_description"] == "Opening street"


def test_move_scene_rejects_invalid_offset_and_handles_boundary():
    timeline = create_timeline_from_visual_plan(plan())
    with pytest.raises(ValueError):
        move_scene(timeline, 0, 2)
    assert move_scene(timeline, 0, -1) == timeline


def test_update_scene_changes_duration_and_text():
    timeline = create_timeline_from_visual_plan(plan())
    updated = update_scene(timeline, 0, duration_seconds=8.5, narration="New voice", subtitle_text="New subtitle")
    assert updated["scenes"][0]["duration_seconds"] == 8.5
    assert updated["scenes"][0]["narration"] == "New voice"
    assert updated["scenes"][0]["subtitle_text"] == "New subtitle"


@pytest.mark.parametrize("duration", [0, 0.1, 180.1, float("nan")])
def test_update_scene_rejects_invalid_duration(duration):
    with pytest.raises(ValueError):
        update_scene(create_timeline_from_visual_plan(plan()), 0, duration_seconds=duration)


def test_save_timeline_persists_draft_only(tmp_path):
    campaign = tmp_path / "proj-1" / "campaigns" / "campaign-1"
    campaign.mkdir(parents=True)
    timeline = create_timeline_from_visual_plan(plan())
    path = save_timeline(timeline, root=tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.parent == campaign / "timelines"
    assert saved["status"] == "draft"
    assert saved["render_authorized"] is False
    assert saved["publishing_authorized"] is False


def test_save_timeline_rejects_duplicate_scene_ids_and_path_traversal(tmp_path):
    campaign = tmp_path / "proj-1" / "campaigns" / "campaign-1"
    campaign.mkdir(parents=True)
    timeline = create_timeline_from_visual_plan(plan())
    timeline["scenes"][1]["scene_id"] = timeline["scenes"][0]["scene_id"]
    with pytest.raises(ValueError, match="unique"):
        save_timeline(timeline, root=tmp_path)
    timeline = create_timeline_from_visual_plan(plan())
    timeline["project_id"] = "../outside"
    with pytest.raises(ValueError, match="Invalid project ID"):
        save_timeline(timeline, root=tmp_path)


def test_load_saved_timeline_matches_script_hash(tmp_path):
    campaign = tmp_path / "proj-1" / "campaigns" / "campaign-1"
    campaign.mkdir(parents=True)
    timeline = create_timeline_from_visual_plan(plan())
    save_timeline(timeline, root=tmp_path)
    loaded = load_timeline("proj-1", "campaign-1", "script-1", "a" * 64, root=tmp_path)
    assert loaded["scenes"][0]["narration"] == "Welcome"
    assert load_timeline("proj-1", "campaign-1", "script-1", "b" * 64, root=tmp_path) is None


def test_timeline_visual_blocks_are_proportional_and_selectable_by_index():
    scenes = [{"duration_seconds": 5}, {"duration_seconds": 10}, {"duration_seconds": 2}]
    blocks = timeline_visual_blocks(scenes, pixels_per_second=20, minimum_width=40, gap=5)
    assert [b["index"] for b in blocks] == [0, 1, 2]
    assert blocks[0]["width"] == 100
    assert blocks[1]["width"] == 200
    assert blocks[2]["width"] == 40
    assert blocks[1]["x"] == blocks[0]["x"] + blocks[0]["width"] + 5


def test_timeline_visual_blocks_validate_dimensions_and_duration():
    with pytest.raises(ValueError):
        timeline_visual_blocks([{"duration_seconds": 181}])
    with pytest.raises(ValueError):
        timeline_visual_blocks([{"duration_seconds": 5}], pixels_per_second=0)


def test_subtitle_timing_must_fit_scene_duration():
    from scripts.timeline_plan import update_subtitle_timing
    timeline={"scenes":[{"duration_seconds":5,"subtitle_text":"Hola"}]}
    result=update_subtitle_timing(timeline,0,start_seconds=1,end_seconds=4.5)
    assert result["scenes"][0]["subtitle_start_seconds"]==1
    assert result["scenes"][0]["subtitle_end_seconds"]==4.5
    with pytest.raises(ValueError,match="fit inside"):
        update_subtitle_timing(timeline,0,start_seconds=1,end_seconds=6)
    with pytest.raises(ValueError,match="fit inside"):
        update_subtitle_timing(timeline,0,start_seconds=4,end_seconds=2)


def test_subtitle_timing_rejects_non_finite_values():
    from scripts.timeline_plan import update_subtitle_timing
    timeline={"scenes":[{"duration_seconds":5,"subtitle_text":"Hola"}]}
    with pytest.raises(ValueError,match="finite"):
        update_subtitle_timing(timeline,0,start_seconds=float("nan"),end_seconds=2)


def test_scene_transition_metadata_and_validation():
    from scripts.timeline_plan import update_scene_transition
    timeline={"scenes":[{"duration_seconds":5,"visual_description":"Scene 1"},{"duration_seconds":4,"visual_description":"Scene 2"}]}
    result=update_scene_transition(timeline,1,transition="fade",duration_seconds=1.25)
    assert result["scenes"][1]["transition_in"]=="fade"
    assert result["scenes"][1]["transition_duration_seconds"]==1.25
    assert result["scenes"][0].get("transition_in") is None
    with pytest.raises(ValueError,match="zero"):
        update_scene_transition(timeline,0,transition="cut",duration_seconds=0.2)
    with pytest.raises(ValueError,match="fit inside"):
        update_scene_transition(timeline,0,transition="dissolve",duration_seconds=6)
    with pytest.raises(ValueError,match="Unsupported"):
        update_scene_transition(timeline,0,transition="wipe",duration_seconds=1)
