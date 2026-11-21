"""Read-only searchable catalog of downloaded campaign media assets."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any
from scripts.project_registry import default_projects_root, list_projects, get_project
from scripts.campaign_registry import list_campaigns, get_campaign
from scripts.media_registry import media_review_status, _campaign_file, _read_candidates, _candidate_hash
from scripts.artifact_registry import _reject_symlink_components

class MediaLibraryError(ValueError):
    """Media library cannot safely catalog or verify local assets."""

def _read_download_ledger(campaign_file: Path) -> list[dict[str, Any]]:
    ledger=campaign_file.parent/"media_download_ledger.jsonl"
    _reject_symlink_components(ledger)
    if not ledger.exists(): return []
    if not ledger.is_file(): raise MediaLibraryError("Download ledger is not a regular file.")
    rows=[]
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            item=json.loads(line)
            if not isinstance(item,dict) or item.get("schema_version")!=1 or item.get("event_type")!="approved_media_download":
                raise MediaLibraryError("Download ledger contains an invalid record.")
            cid=item.get("candidate_id","")
            if not isinstance(cid,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",cid):
                raise MediaLibraryError("Download ledger contains an unsafe candidate ID.")
            if not re.fullmatch(r"[a-f0-9]{64}",item.get("candidate_sha256","")) or not re.fullmatch(r"[a-f0-9]{64}",item.get("sha256","")):
                raise MediaLibraryError("Download ledger contains invalid hash fields.")
            rows.append(item)
    except (OSError,UnicodeError,json.JSONDecodeError):
        raise MediaLibraryError("Download ledger is malformed or unreadable.") from None
    return rows

def _hash_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""): digest.update(block)
    return digest.hexdigest()

def _catalog_campaign(project_id: str, campaign_id: str, campaign_file: Path, projects_root: Path) -> list[dict[str,Any]]:
    rows=_read_download_ledger(campaign_file)
    campaign_root=campaign_file.parent.resolve()
    assets_dir=campaign_root/"media_assets"
    candidates=_read_candidates(campaign_file)
    results=[]
    for record in rows:
        cid=record["candidate_id"]
        candidate=candidates.get(cid,{})
        metadata_current=bool(candidate) and _candidate_hash(candidate)==record["candidate_sha256"]
        rel=record.get("local_path")
        local_path=None
        integrity="invalid_path"
        path_parts=Path(rel).parts if isinstance(rel,str) else ()
        if path_parts and not Path(rel).is_absolute() and len(path_parts)==2 and path_parts[0]=="media_assets" and path_parts[1] not in {".",".."}:
            local_path=campaign_root/rel
            try:
                _reject_symlink_components(local_path)
                resolved_assets=assets_dir.resolve(strict=True)
                resolved=local_path.resolve(strict=True)
                if not resolved.is_file() or not resolved.is_relative_to(resolved_assets): integrity="outside_library"
                else:
                    integrity="verified" if _hash_file(resolved)==record["sha256"] else "hash_mismatch"
                    local_path=resolved
            except (OSError,ValueError,RuntimeError): integrity="missing_or_unsafe"
        rights=media_review_status(project_id,campaign_id,cid,root=projects_root)
        approved=rights=="reviewed_approved"
        results.append({
            "project_id":project_id,"campaign_id":campaign_id,"candidate_id":cid,
            "candidate_sha256":record["candidate_sha256"],"file_sha256":record["sha256"],
            "local_path":str(local_path) if local_path else str(rel or ""),
            "size_bytes":record.get("size_bytes"),"downloaded_at":record.get("downloaded_at"),
            "title":candidate.get("title",record.get("title","")),"creator":candidate.get("creator",record.get("creator","")),
            "width":candidate.get("width"),"height":candidate.get("height"),
            "license":record.get("license",candidate.get("license","")),"license_url":record.get("license_url",candidate.get("license_url","")),
            "attribution":record.get("attribution",candidate.get("attribution","")),
            "source_page_url":record.get("source_page_url",candidate.get("source_page_url","")),
            "source_url":record.get("source_url",candidate.get("image_url","")),
            "rights_status":rights,"metadata_current":metadata_current,"integrity_status":integrity,
            "usable_for_selection":integrity=="verified" and approved and metadata_current})
    return results

def list_media_assets(*, project_id: str|None=None, campaign_id: str|None=None, root: Path|None=None) -> list[dict[str,Any]]:
    projects_root=(root or default_projects_root()).expanduser().resolve()
    projects=[get_project(project_id,projects_root)] if project_id else list_projects(projects_root)
    output=[]
    for project in projects:
        pid=project["project_id"]
        campaigns=[get_campaign(pid,campaign_id,projects_root)] if campaign_id else list_campaigns(pid,projects_root)
        for campaign in campaigns:
            if campaign.get("project_id")!=pid: raise MediaLibraryError("Campaign/project identity mismatch.")
            cf=_campaign_file(pid,campaign["campaign_id"],projects_root)
            output.extend(_catalog_campaign(pid,campaign["campaign_id"],cf,projects_root))
    return sorted(output,key=lambda x:(x["project_id"],x["campaign_id"],x["candidate_id"],x["downloaded_at"] or ""))

def search_media_assets(query: str, *, project_id: str|None=None, campaign_id: str|None=None, root: Path|None=None) -> list[dict[str,Any]]:
    terms=query.casefold().split()
    if not terms: raise MediaLibraryError("Search query must not be empty.")
    items=list_media_assets(project_id=project_id,campaign_id=campaign_id,root=root)
    fields=("title","creator","license","attribution","project_id","campaign_id","candidate_id","source_page_url")
    return [item for item in items if all(term in " ".join(str(item.get(k,"")) for k in fields).casefold() for term in terms)]

def verify_media_library(*, project_id: str|None=None, campaign_id: str|None=None, root: Path|None=None) -> dict[str,Any]:
    items=list_media_assets(project_id=project_id,campaign_id=campaign_id,root=root)
    issues=[item for item in items if item["integrity_status"]!="verified" or item["rights_status"]!="reviewed_approved" or not item["metadata_current"]]
    return {"status":"PASS" if not issues else "BLOCKED","asset_count":len(items),
        "verified_count":sum(x["integrity_status"]=="verified" for x in items),
        "current_approved_count":sum(x["rights_status"]=="reviewed_approved" for x in items),
        "metadata_current_count":sum(x["metadata_current"] for x in items),
        "usable_count":sum(x["usable_for_selection"] for x in items),"blocked_count":len(issues),
        "issues":[{"project_id":x["project_id"],"campaign_id":x["campaign_id"],"candidate_id":x["candidate_id"],
        "integrity_status":x["integrity_status"],"rights_status":x["rights_status"],"metadata_current":x["metadata_current"]} for x in issues]}
