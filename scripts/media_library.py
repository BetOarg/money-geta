"""Read-only searchable catalog of downloaded campaign media assets."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.project_registry import default_projects_root, list_projects, get_project
from scripts.campaign_registry import list_campaigns, get_campaign
from scripts.media_registry import media_review_status, _campaign_file
from scripts.artifact_registry import _reject_symlink_components


class MediaLibraryError(ValueError):
    """Media library cannot safely catalog or verify local assets."""


def _read_download_ledger(campaign_file: Path) -> list[dict[str, Any]]:
    ledger = campaign_file.parent / "media_download_ledger.jsonl"
    _reject_symlink_components(ledger)
    if not ledger.exists():
        return []
    if not ledger.is_file():
        raise MediaLibraryError("Download ledger is not a regular file.")
    rows = []
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict) or item.get("schema_version") != 1 or item.get("event_type") != "approved_media_download":
                raise MediaLibraryError("Download ledger contains an invalid record.")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item.get("candidate_id", "")):
                raise MediaLibraryError("Download ledger contains an unsafe candidate ID.")
            if not re.fullmatch(r"[a-f0-9]{64}", item.get("candidate_sha256", "")) or not re.fullmatch(r"[a-f0-9]{64}", item.get("sha256", "")):
                raise MediaLibraryError("Download ledger contains invalid hash fields.")
            rows.append(item)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise MediaLibraryError("Download ledger is malformed or unreadable.") from None
    return rows


def _catalog_campaign(project_id: str, campaign_id: str, campaign_file: Path) -> list[dict[str, Any]]:
    rows = _read_download_ledger(campaign_file)
    root = campaign_file.parent.resolve()
    results = []
    for record in rows:
        local_rel = record.get("local_path")
        if not isinstance(local_rel, str) or not local_rel or Path(local_rel).is_absolute():
            local_path = None
            integrity = "invalid_path"
        else:
            local_path = root / local_rel
            try:
                _reject_symlink_components(local_path)
                resolved = local_path.resolve(strict=True)
                assets = (root / "media_assets").resolve(strict=True)
                if not resolved.is_relative_to(assets) or not resolved.is_file():
                    integrity = "outside_library"
                else:
                    actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
                    integrity = "verified" if actual == record["sha256"] else "hash_mismatch"
                    local_path = resolved
            except (OSError, ValueError, RuntimeError):
                integrity = "missing_or_unsafe"
        status = media_review_status(project_id, campaign_id, record["candidate_id"])
        current_approved = status == "reviewed_approved"
        results.append({
            "project_id": project_id,
            "campaign_id": campaign_id,
            "candidate_id": record["candidate_id"],
            "candidate_sha256": record["candidate_sha256"],
            "file_sha256": record["sha256"],
            "local_path": str(local_path) if local_path else local_rel,
            "size_bytes": record.get("size_bytes"),
            "downloaded_at": record.get("downloaded_at"),
            "title": record.get("title", ""),
            "creator": record.get("creator", ""),
            "license": record.get("license", ""),
            "license_url": record.get("license_url", ""),
            "attribution": record.get("attribution", ""),
            "source_page_url": record.get("source_page_url", ""),
            "source_url": record.get("source_url", ""),
            "rights_status": status,
            "integrity_status": integrity,
            "usable_for_selection": integrity == "verified" and current_approved,
        })
    return results


def list_media_assets(*, project_id: str | None = None, campaign_id: str | None = None,
                      root: Path | None = None) -> list[dict[str, Any]]:
    projects_root = (root or default_projects_root()).expanduser().resolve()
    projects = [get_project(project_id, projects_root)] if project_id else list_projects(projects_root)
    output = []
    for project in projects:
        pid = project["project_id"]
        campaigns = [get_campaign(pid, campaign_id, projects_root)] if campaign_id else list_campaigns(pid, projects_root)
        for campaign in campaigns:
            if campaign.get("project_id") != pid:
                raise MediaLibraryError("Campaign/project identity mismatch.")
            campaign_file = _campaign_file(pid, campaign["campaign_id"], projects_root)
            output.extend(_catalog_campaign(pid, campaign["campaign_id"], campaign_file))
    return sorted(output, key=lambda item: (item["project_id"], item["campaign_id"], item["candidate_id"], item["downloaded_at"] or ""))


def search_media_assets(query: str, *, project_id: str | None = None, campaign_id: str | None = None,
                       root: Path | None = None) -> list[dict[str, Any]]:
    terms = [term for term in query.casefold().split() if term]
    if not terms:
        raise MediaLibraryError("Search query must not be empty.")
    assets = list_media_assets(project_id=project_id, campaign_id=campaign_id, root=root)
    def haystack(item: dict[str, Any]) -> str:
        return " ".join(str(item.get(key, "")) for key in ("title", "creator", "license", "attribution", "project_id", "campaign_id", "candidate_id", "source_page_url")).casefold()
    return [item for item in assets if all(term in haystack(item) for term in terms)]


def verify_media_library(*, project_id: str | None = None, campaign_id: str | None = None,
                        root: Path | None = None) -> dict[str, Any]:
    items = list_media_assets(project_id=project_id, campaign_id=campaign_id, root=root)
    failures = [item for item in items if item["integrity_status"] != "verified" or item["rights_status"] != "reviewed_approved"]
    return {
        "status": "PASS" if not failures else "BLOCKED",
        "asset_count": len(items),
        "verified_count": sum(item["integrity_status"] == "verified" for item in items),
        "current_approved_count": sum(item["rights_status"] == "reviewed_approved" for item in items),
        "usable_count": sum(item["usable_for_selection"] for item in items),
        "blocked_count": len(failures),
        "issues": [{"project_id": item["project_id"], "campaign_id": item["campaign_id"],
                    "candidate_id": item["candidate_id"], "integrity_status": item["integrity_status"],
                    "rights_status": item["rights_status"]} for item in failures],
    }
