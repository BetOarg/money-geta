import hashlib, json
from pathlib import Path

import pytest

from scripts.project_registry import create_project
from scripts.campaign_registry import create_campaign
from scripts.providers.openverse import _normalize, save_image_candidates
from scripts.media_registry import review_media_candidate, _campaign_file, _candidate_hash
from scripts.media_library import list_media_assets, search_media_assets, verify_media_library
from scripts.money_geta import main


def fixture(tmp_path):
    root=tmp_path/"projects"
    create_project("Library project","viral",root=root)
    create_campaign("library-project","Campaign","YouTube Shorts",root=root)
    raw={"title":"Golden sunset","url":"https://cdn.example/image.png","foreign_landing_url":"https://source.example/golden",
        "creator":"Artist A","creator_url":"https://source.example/artist","license":"by","license_version":"4.0",
        "license_url":"https://creativecommons.org/licenses/by/4.0/","source":"Openverse","category":"photograph",
        "thumbnail":"https://cdn.example/thumb.jpg","width":1200,"height":800,"attribution":"Artist A"}
    cand=_normalize("sunset", [raw])[0]
    save_image_candidates("library-project","campaign",[cand],root=root)
    review_media_candidate("library-project","campaign",cand["candidate_id"],decision="approved",reviewer="Tester",
        rights_evidence="Original source license page checked",reviewed_license="CC BY 4.0",attribution="Artist A",
        source_reviewed=True,root=root)
    cf=_campaign_file("library-project","campaign",root)
    asset_dir=cf.parent/"media_assets"
    asset_dir.mkdir()
    data=b"\\x89PNG\\r\\n\\x1a\\nvalid test payload"
    asset=asset_dir/(cand["candidate_id"]+".png")
    asset.write_bytes(data)
    record={"schema_version":1,"event_type":"approved_media_download","candidate_id":cand.candidate_id,
        "candidate_sha256":_candidate_hash(cand),"source_url":cand["image_url"],"source_page_url":cand["source_page_url"],
        "license":cand["license"],"license_url":cand["license_url"],"creator":cand["creator"],"attribution":cand["attribution"],
        "local_path":"media_assets/"+asset.name,"sha256":hashlib.sha256(data).hexdigest(),"size_bytes":len(data),"downloaded_at":"2026-11-21T12:00:00Z"}
    (cf.parent/"media_download_ledger.jsonl").write_text(json.dumps(record)+"\\n",encoding="utf-8")
    return root,cf,cand,record,asset


def test_catalog_lists_current_verified_rights_asset(tmp_path):
    root,cf,cand,record,asset=fixture(tmp_path)
    items=list_media_assets(root=root)
    assert len(items)==1
    item=items[0]
    assert item["candidate_id"]==cand.candidate_id
    assert item["integrity_status"]=="verified"
    assert item["rights_status"]=="reviewed_approved"
    assert item["metadata_current"] is True
    assert item["usable_for_selection"] is True
    assert item["title"]=="Golden sunset"
    assert item["local_path"]==str(asset.resolve())


def test_search_matches_multiple_metadata_terms(tmp_path):
    root,_,_,_,_=fixture(tmp_path)
    found=search_media_assets("golden artist",root=root)
    assert len(found)==1 and found[0]["creator"]=="Artist A"
    assert search_media_assets("missing keyword",root=root)==[]


def test_verify_detects_hash_mismatch(tmp_path):
    root,cf,cand,record,asset=fixture(tmp_path)
    asset.write_bytes(b"tampered file")
    report=verify_media_library(root=root)
    assert report["status"]=="BLOCKED"
    assert report["blocked_count"]==1
    assert report["issues"][0]["integrity_status"]=="hash_mismatch"


def test_verify_detects_stale_candidate_rights(tmp_path):
    root,cf,cand,record,asset=fixture(tmp_path)
    candidates=cf.parent/"media_candidates.jsonl"
    item=json.loads(candidates.read_text(encoding="utf-8"))
    item["attribution"]="Changed metadata"
    candidates.write_text(json.dumps(item)+"\\n",encoding="utf-8")
    report=verify_media_library(root=root)
    assert report["status"]=="BLOCKED"
    assert report["issues"][0]["metadata_current"] is False
    assert report["issues"][0]["rights_status"]=="review_stale"


def test_cli_asset_library_list_search_verify(tmp_path,monkeypatch,capsys):
    root,_,cand,_,_=fixture(tmp_path)
    monkeypatch.setenv("MONEY_GETA_PROJECTS_DIR",str(root))
    assert main(["asset-library","list","--project","library-project"])==0
    assert cand.candidate_id in capsys.readouterr().out
    assert main(["asset-library","search","--query","Golden sunset","--campaign","campaign"])==0
    assert cand.candidate_id in capsys.readouterr().out
    assert main(["asset-library","verify","--project","library-project"])==0
    out=capsys.readouterr().out
    assert "MEDIA_LIBRARY: PASS" in out and '"usable_count": 1' in out


def test_empty_search_rejected():
    with pytest.raises(ValueError,match="must not be empty"):
        search_media_assets("  ")
