import json
from pathlib import Path

import pytest

from scripts.scene_asset_matcher import tokenize, match_scene, build_scene_asset_plan


def assets():
    return [
        {"candidate_id":"a","title":"Neon city street","creator":"Photo A","usable_for_selection":True,
         "local_path":"assets/a.jpg","file_sha256":"a"*64,"rights_status":"reviewed_approved",
         "integrity_status":"verified","metadata_current":True,"license":"CC BY"},
        {"candidate_id":"b","title":"Quiet beach sunrise","creator":"Photo B","usable_for_selection":True,
         "local_path":"assets/b.jpg","file_sha256":"b"*64,"rights_status":"reviewed_approved",
         "integrity_status":"verified","metadata_current":True,"license":"CC BY"},
        {"candidate_id":"c","title":"Neon city skyline","usable_for_selection":False,
         "local_path":"assets/c.jpg","rights_status":"review_stale","integrity_status":"verified",
         "metadata_current":False,"license":"CC BY"},
    ]


def test_tokenization_normalizes_accents_and_filters_common_words():
    assert tokenize("La ciudad está iluminada por neón") == {"ciudad","iluminada","neon"}


def test_match_scene_prioritizes_visual_overlap_and_excludes_unusable():
    scene={"visual":"neon city street","narration":"The city lights shine at night"}
    results=match_scene(scene,assets(),limit=3)
    assert [item["candidate_id"] for item in results] == ["a"]
    assert results[0]["matched_visual_terms"] == ["neon","street"] or results[0]["matched_visual_terms"] == ["city","neon","street"]
    assert all(item["candidate_id"]!="c" for item in results)


def test_match_scene_is_deterministic_and_limited():
    scene={"visual":"beach sunrise","narration":"waves"}
    rows=match_scene(scene,assets(),limit=1)
    assert rows == match_scene(scene,assets(),limit=1)
    assert len(rows) == 1 and rows[0]["candidate_id"] == "b"


def test_empty_scene_terms_return_no_suggestions():
    assert match_scene({"visual":"","narration":""},assets()) == []


def test_plan_requires_current_approval_and_matching_hash(monkeypatch,tmp_path):
    import scripts.scene_asset_matcher as matcher
    draft_dir=tmp_path/"proj"/"campaigns"/"camp"/"drafts"
    draft_dir.mkdir(parents=True)
    script_path=draft_dir/"approved.json"
    script_path.write_text(json.dumps({"script":{"scenes":[{"visual":"neon street","narration":"night city"}]}}),encoding="utf-8")
    registration={"script_id":"s-1","sha256":"d"*64,"path":str(script_path)}
    monkeypatch.setattr(matcher,"list_scripts",lambda *a,**k:[registration])
    monkeypatch.setattr(matcher,"check_script",lambda *a,**k:(False,["approval stale"]))
    monkeypatch.setattr(matcher,"list_media_assets",lambda *a,**k:assets())
    with pytest.raises(ValueError,match="currently approved"):
        build_scene_asset_plan("proj","camp","s-1","d"*64,root=tmp_path)


def test_plan_outputs_suggestions_only_and_approval_gate(monkeypatch,tmp_path):
    import scripts.scene_asset_matcher as matcher
    draft_dir=tmp_path/"proj"/"campaigns"/"camp"/"drafts"
    draft_dir.mkdir(parents=True)
    script_path=draft_dir/"approved.json"
    script_path.write_text(json.dumps({"script":{"scenes":[{"visual":"neon street","narration":"night city"}]}}),encoding="utf-8")
    registration={"script_id":"s-1","sha256":"d"*64,"path":str(script_path)}
    monkeypatch.setattr(matcher,"list_scripts",lambda *a,**k:[registration])
    monkeypatch.setattr(matcher,"check_script",lambda *a,**k:(True,[]))
    monkeypatch.setattr(matcher,"list_media_assets",lambda *a,**k:assets())
    report=build_scene_asset_plan("proj","camp","s-1","d"*64,root=tmp_path)
    assert report["status"]=="suggestions_only"
    assert report["scenes"][0]["suggestions"][0]["candidate_id"]=="a"
    assert report["human_review_required"] is True
    assert report["render_authorized"] is False
    assert report["publishing_authorized"] is False


def test_plan_rejects_script_outside_campaign_drafts(monkeypatch,tmp_path):
    import scripts.scene_asset_matcher as matcher
    outside=tmp_path/"outside.json"
    outside.write_text(json.dumps({"script":{"scenes":[{"visual":"test","narration":"test"}]}}),encoding="utf-8")
    registration={"script_id":"s-1","sha256":"d"*64,"path":str(outside)}
    monkeypatch.setattr(matcher,"list_scripts",lambda *a,**k:[registration])
    monkeypatch.setattr(matcher,"check_script",lambda *a,**k:(True,[]))
    with pytest.raises(ValueError,match="inside the campaign drafts"):
        build_scene_asset_plan("proj","camp","s-1","d"*64,root=tmp_path)
