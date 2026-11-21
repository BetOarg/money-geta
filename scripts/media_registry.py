"""Append-only, hash-bound operator review records for campaign image candidates."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.project_registry import default_projects_root, get_project
from scripts.campaign_registry import get_campaign
from scripts.artifact_registry import _reject_symlink_components


class MediaReviewError(ValueError):
    """Media review cannot be safely recorded or checked."""


def _campaign_file(project_id: str, campaign_id: str, root: Path | None = None) -> Path:
    projects_root = (root or default_projects_root()).expanduser().resolve()
    get_project(project_id, projects_root)
    get_campaign(project_id, campaign_id, projects_root)
    path = projects_root / project_id / "campaigns" / campaign_id / "campaign.json"
    _reject_symlink_components(path)
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(projects_root):
        raise MediaReviewError("Campaign manifest must be inside the projects root.")
    return resolved


def _candidate_ledger(campaign_file: Path) -> Path:
    path = campaign_file.parent / "media_candidates.jsonl"
    _reject_symlink_components(path)
    if not path.exists() or not path.is_file():
        raise MediaReviewError("No image candidate ledger exists for this campaign.")
    return path


def _read_candidates(campaign_file: Path) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    try:
        for line in _candidate_ledger(campaign_file).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict) or not isinstance(item.get("candidate_id"), str):
                raise MediaReviewError("Image candidate ledger contains malformed records.")
            candidates[item["candidate_id"]] = item
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise MediaReviewError("Image candidate ledger is malformed or unreadable.") from None
    return candidates


def _candidate_hash(candidate: dict[str, Any]) -> str:
    from scripts.providers.openverse import candidate_metadata_hash
    return candidate_metadata_hash(candidate)


def _review_ledger(campaign_file: Path) -> Path:
    path = campaign_file.parent / "media_review_ledger.jsonl"
    _reject_symlink_components(path)
    return path


def _read_reviews(campaign_file: Path) -> list[dict[str, Any]]:
    path = _review_ledger(campaign_file)
    if not path.exists():
        return []
    if not path.is_file():
        raise MediaReviewError("Media review ledger is not a regular file.")
    events = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or event.get("schema_version") != 1 or event.get("event_type") != "media_review":
                raise MediaReviewError("Media review ledger contains invalid events.")
            if not isinstance(event.get("candidate_id"), str) or not re.fullmatch(r"[a-f0-9]{64}", event.get("candidate_sha256", "")):
                raise MediaReviewError("Media review ledger event lacks valid identity/hash.")
            if event.get("decision") not in {"approved", "rejected"} or not isinstance(event.get("reviewer"), str) or not event["reviewer"].strip():
                raise MediaReviewError("Media review event has invalid decision or reviewer.")
            events.append(event)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise MediaReviewError("Media review ledger is malformed or unreadable.") from None
    return events


def review_media_candidate(project_id: str, campaign_id: str, candidate_id: str, *,
                         decision: str, reviewer: str, rights_evidence: str = "",
                         reviewed_license: str = "", attribution: str = "",
                         source_reviewed: bool = False, notes: str = "",
                         root: Path | None = None) -> dict[str, Any]:
    if decision not in {"approved", "rejected"}:
        raise MediaReviewError("Decision must be approved or rejected.")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer.strip()) > 120:
        raise MediaReviewError("Reviewer must be 1–120 characters.")
    if len(rights_evidence) > 2000 or len(reviewed_license) > 200 or len(attribution) > 1000 or len(notes) > 2000:
        raise MediaReviewError("Rights evidence, license, attribution or notes exceed length limits.")
    campaign_file = _campaign_file(project_id, campaign_id, root)
    candidates = _read_candidates(campaign_file)
    candidate = candidates.get(candidate_id)
    if candidate is None:
        raise MediaReviewError("Candidate ID was not found in this campaign.")
    source_url = candidate.get("source_page_url")
    license_url = candidate.get("license_url")
    license_name = candidate.get("license")
    if not isinstance(source_url, str) or not isinstance(license_name, str) or not license_name.strip():
        raise MediaReviewError("Candidate lacks source or license metadata; cannot record a review.")
    if decision == "approved" and (not source_reviewed or not rights_evidence.strip() or not reviewed_license.strip() or not license_url):
        raise MediaReviewError("Approval requires explicit source-page review, rights evidence, verified license text and license URL.")
    event = {
        "schema_version": 1, "event_type": "media_review",
        "candidate_id": candidate_id, "candidate_sha256": _candidate_hash(candidate),
        "source_page_url": source_url, "provider_license": license_name,
        "reviewed_license": reviewed_license.strip(), "license_url": license_url,
        "attribution": attribution.strip() or candidate.get("attribution", ""),
        "rights_evidence": rights_evidence.strip(), "source_reviewed": bool(source_reviewed),
        "decision": decision, "reviewer": reviewer.strip(), "notes": notes.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    ledger = _review_ledger(campaign_file)
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


def check_media_candidate(project_id: str, campaign_id: str, candidate_id: str, *,
                        root: Path | None = None) -> tuple[bool, list[str]]:
    try:
        campaign_file = _campaign_file(project_id, campaign_id, root)
        candidate = _read_candidates(campaign_file).get(candidate_id)
        if candidate is None:
            raise MediaReviewError("Candidate ID was not found.")
        reviews = [event for event in _read_reviews(campaign_file) if event["candidate_id"] == candidate_id]
        if not reviews:
            return False, ["rights review is pending"]
        latest = reviews[-1]
        if latest.get("candidate_sha256") != _candidate_hash(candidate):
            return False, ["candidate metadata changed; rights review is stale"]
        if latest.get("decision") != "approved" or not latest.get("source_reviewed") or not latest.get("rights_evidence") or not latest.get("reviewed_license"):
            return False, ["rights review is rejected or incomplete"]
        return True, []
    except (OSError, ValueError, RuntimeError) as exc:
        return False, [str(exc)]
