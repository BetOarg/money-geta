"""Append-only, hash-bound review registry for generated script drafts."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.campaign_check import check_file
from scripts.campaign_registry import get_campaign
from scripts.claim_registry import list_claims
from scripts.project_registry import default_projects_root, get_project
from scripts.scriptwriter import _read_source_ledger, validate_script_payload


class ScriptReviewError(ValueError):
    """A script review action cannot safely be applied."""


def _paths(project_id: str, campaign_id: str, root: Path | None = None) -> tuple[Path, Path]:
    projects_root = (root or default_projects_root()).expanduser().resolve()
    project_file = projects_root / project_id / "project.json"
    campaign_file = projects_root / project_id / "campaigns" / campaign_id / "campaign.json"
    from scripts.artifact_registry import _reject_symlink_components
    _reject_symlink_components(project_file)
    _reject_symlink_components(campaign_file)
    project = get_project(project_id, projects_root)
    campaign = get_campaign(project_id, campaign_id, projects_root)
    campaign_path = campaign_file.resolve(strict=True)
    if not campaign_path.is_file() or not campaign_path.is_relative_to(projects_root):
        raise ScriptReviewError("Campaign manifest must be inside the local projects root.")
    passed, problems = check_file(campaign_path)
    if not passed:
        raise ScriptReviewError("Campaign gate blocked script review: " + "; ".join(problems))
    return campaign_path, projects_root


def _script_data(campaign_path: Path, script_path: Path, project_id: str, campaign_id: str) -> dict[str, Any]:
    from scripts.artifact_registry import _reject_symlink_components
    _reject_symlink_components(script_path)
    script_file = script_path.expanduser().resolve(strict=True)
    draft_root = (campaign_path.parent / "drafts").resolve(strict=True)
    if not script_file.is_file() or not script_file.is_relative_to(draft_root):
        raise ScriptReviewError("Script draft must be a regular file inside the campaign drafts directory.")
    try:
        report = json.loads(script_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ScriptReviewError("Script draft JSON is malformed or unreadable.") from None
    if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("status") != "draft":
        raise ScriptReviewError("Script draft must use schema v1 and draft status.")
    if report.get("project_id") != project_id or report.get("campaign_id") != campaign_id:
        raise ScriptReviewError("Draft identity does not match the selected project/campaign.")
    approval = report.get("approval")
    if not isinstance(approval, dict) or approval.get("status") != "pending" or approval.get("approved_sha256") is not None:
        raise ScriptReviewError("Draft approval metadata is not pending; registry decisions are authoritative.")
    documents = _read_source_ledger(campaign_path.parent / "source_ledger.jsonl")
    evidence_ids = {item["evidence_id"] for item in documents}
    claims = list_claims(project_id, campaign_id, root=campaign_path.parents[3])
    if any(item.get("status") != "supported" for item in claims):
        raise ScriptReviewError("Unresolved factual claims block script registration/approval.")
    script = report.get("script")
    if not isinstance(script, dict) or report.get("source_ids") != script.get("source_ids"):
        raise ScriptReviewError("Draft top-level source IDs do not match script source IDs.")
    validated = validate_script_payload(script, evidence_ids=evidence_ids,
        supported_claims=claims, factual_required=get_campaign(project_id, campaign_id, campaign_path.parents[3]).get("factual_claims_required") is True)
    return {"report": report, "script": validated, "path": script_file, "sha256": hashlib.sha256(script_file.read_bytes()).hexdigest()}


def _read_events(campaign_path: Path) -> list[dict[str, Any]]:
    ledger = campaign_path.parent / "script_ledger.jsonl"
    if ledger.is_symlink():
        raise ScriptReviewError("Script review ledger symlinks are blocked.")
    if not ledger.exists():
        return []
    if not ledger.is_file():
        raise ScriptReviewError("Script review ledger is not a regular file.")
    events = []
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or event.get("schema_version") != 1 or event.get("event_type") not in {"script_registered", "script_decision"}:
                raise ScriptReviewError("Script review ledger contains an invalid event.")
            if not isinstance(event.get("script_id"), str) or not event["script_id"] or not isinstance(event.get("sha256"), str):
                raise ScriptReviewError("Script review ledger event lacks identity/hash.")
            events.append(event)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ScriptReviewError("Script review ledger is malformed.") from None
    return events


def _append_event(campaign_path: Path, event: dict[str, Any]) -> None:
    from scripts.artifact_registry import _reject_symlink_components
    ledger = campaign_path.parent / "script_ledger.jsonl"
    _reject_symlink_components(ledger)
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def register_script(project_id: str, campaign_id: str, draft_path: Path, *, root: Path | None = None) -> dict[str, Any]:
    campaign_path, projects_root = _paths(project_id, campaign_id, root)
    validated = _script_data(campaign_path, draft_path, project_id, campaign_id)
    events = _read_events(campaign_path)
    existing = next((event for event in events if event.get("event_type") == "script_registered"
                    and event.get("path") == str(validated["path"]) and event.get("sha256") == validated["sha256"]), None)
    if existing:
        return existing
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "schema_version": 1, "event_type": "script_registered", "script_id": "script-" + uuid.uuid4().hex,
        "project_id": project_id, "campaign_id": campaign_id, "path": str(validated["path"]),
        "sha256": validated["sha256"], "input_sha256": validated["report"].get("input_sha256"),
        "source_ids": validated["report"].get("source_ids", []), "registered_at": now,
    }
    _append_event(campaign_path, event)
    return event


def list_scripts(project_id: str, campaign_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    campaign_path, _ = _paths(project_id, campaign_id, root)
    events = _read_events(campaign_path)
    registrations: dict[str, dict[str, Any]] = {}
    for event in events:
        script_id = event["script_id"]
        if event["event_type"] == "script_registered":
            registrations[script_id] = dict(event)
        elif script_id in registrations:
            registrations[script_id]["latest_decision"] = event
    return list(registrations.values())


def _find_registered(campaign_path: Path, script_id: str, sha256: str) -> dict[str, Any]:
    registered = next((event for event in _read_events(campaign_path)
                       if event.get("event_type") == "script_registered" and event.get("script_id") == script_id), None)
    if not registered:
        raise ScriptReviewError("Script ID is not registered for this campaign.")
    if registered.get("sha256") != sha256:
        raise ScriptReviewError("Requested script hash does not match the registered version.")
    path = Path(registered["path"])
    if path.is_symlink() or not path.is_file():
        raise ScriptReviewError("Registered script file is missing or unsafe.")
    current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if current_hash != sha256:
        raise ScriptReviewError("Registered script file changed; hash-bound review is stale.")
    return registered


def approve_script(project_id: str, campaign_id: str, script_id: str, sha256: str, *,
                  reviewer: str, decision: str = "approved", notes: str = "",
                  root: Path | None = None) -> dict[str, Any]:
    if decision not in {"approved", "rejected"}:
        raise ScriptReviewError("Decision must be approved or rejected.")
    if not reviewer.strip() or len(reviewer.strip()) > 120:
        raise ScriptReviewError("Reviewer must be 1–120 characters.")
    if len(notes) > 2000:
        raise ScriptReviewError("Review notes cannot exceed 2000 characters.")
    campaign_path, _ = _paths(project_id, campaign_id, root)
    registered = _find_registered(campaign_path, script_id, sha256)
    _script_data(campaign_path, Path(registered["path"]), project_id, campaign_id)
    event = {
        "schema_version": 1, "event_type": "script_decision", "script_id": script_id,
        "sha256": sha256, "decision": decision, "reviewer": reviewer.strip(),
        "notes": notes.strip(), "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    _append_event(campaign_path, event)
    return event


def check_script(project_id: str, campaign_id: str, script_id: str, sha256: str, *,
                root: Path | None = None) -> tuple[bool, list[str]]:
    try:
        campaign_path, _ = _paths(project_id, campaign_id, root)
        registered = _find_registered(campaign_path, script_id, sha256)
        _script_data(campaign_path, Path(registered["path"]), project_id, campaign_id)
        events = _read_events(campaign_path)
        decisions = [event for event in events if event.get("event_type") == "script_decision" and event.get("script_id") == script_id and event.get("sha256") == sha256]
        latest = decisions[-1] if decisions else None
        if latest is None or latest.get("decision") != "approved":
            return False, ["script approval is pending or rejected"]
        if latest.get("decided_at", "") <= registered.get("registered_at", ""):
            return False, ["script approval must follow registration"]
        return True, []
    except (OSError, ValueError, RuntimeError) as exc:
        return False, [str(exc)]
