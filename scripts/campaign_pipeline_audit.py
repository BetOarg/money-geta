"""Read-only campaign pipeline checkpoint report for the local workspace."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.project_registry import default_projects_root, get_project
from scripts.campaign_registry import get_campaign
from scripts.campaign_check import check_file
from scripts.artifact_registry import _reject_symlink_components


def _safe_campaign_folder(project_id: str, campaign_id: str, root: Path | None) -> tuple[Path, Path]:
    projects_root = (root or default_projects_root()).expanduser().resolve()
    get_project(project_id, projects_root)
    get_campaign(project_id, campaign_id, projects_root)
    manifest = projects_root / project_id / "campaigns" / campaign_id / "campaign.json"
    _reject_symlink_components(manifest)
    resolved = manifest.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(projects_root):
        raise ValueError("Campaign manifest is not a regular file inside the projects root.")
    return projects_root, resolved.parent


def _count_files(folder: Path, pattern: str) -> int:
    _reject_symlink_components(folder)
    if folder.is_symlink() or not folder.is_dir():
        return 0
    return sum(1 for item in folder.glob(pattern) if item.is_file() and not item.is_symlink())


def _read_ledger(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    _reject_symlink_components(path)
    if path.is_symlink():
        return [], f"{path.name}: symlink blocked"
    if not path.exists():
        return [], None
    if not path.is_file():
        return [], f"{path.name}: not a regular file"
    try:
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [], f"{path.name}: malformed or unreadable"
    if any(not isinstance(event, dict) for event in events):
        return [], f"{path.name}: non-object record"
    return events, None


def audit_campaign(project_id: str, campaign_id: str, *, root: Path | None = None) -> dict[str, Any]:
    """Report local checkpoints; presence is not a claim of content quality or approval."""
    projects_root, folder = _safe_campaign_folder(project_id, campaign_id, root)
    manifest = folder / "campaign.json"
    gate_passed, gate_problems = check_file(manifest)
    source_events, source_error = _read_ledger(folder / "source_ledger.jsonl")
    claim_events, claim_error = _read_ledger(folder / "claim_ledger.jsonl")
    script_events, script_error = _read_ledger(folder / "script_ledger.jsonl")
    media_events, media_error = _read_ledger(folder / "media_review_ledger.jsonl")
    artifact_events, artifact_error = _read_ledger(folder / "artifact_ledger.jsonl")
    candidates, candidate_error = _read_ledger(folder / "media_candidates.jsonl")
    event_counts = lambda events: {
        event_type: sum(1 for row in events if row.get("event_type") == event_type)
        for event_type in sorted({row.get("event_type") for row in events if isinstance(row.get("event_type"), str)})
    }
    claims_created = sum(1 for row in claim_events if row.get("event_type") == "claim_created")
    claims_assessed = sum(1 for row in claim_events if row.get("event_type") == "claim_assessed")
    scripts_registered = sum(1 for row in script_events if row.get("event_type") == "script_registered")
    scripts_approved = sum(1 for row in script_events if row.get("event_type") == "script_decision" and row.get("decision") == "approved")
    media_approved = sum(1 for row in media_events if row.get("decision") == "approved")
    artifact_registered = sum(1 for row in artifact_events if row.get("event_type") == "artifact_registered")
    artifact_approved = sum(1 for row in artifact_events if row.get("event_type") == "artifact_approved")
    artifact_qc = sum(1 for row in artifact_events if row.get("event_type") == "artifact_qc" and row.get("passed") is True)
    central_qc_ready = sum(1 for row in artifact_events if row.get("event_type") == "artifact_central_qc" and row.get("status") == "READY_FOR_HUMAN_REVIEW")
    stages = [
        {"stage": "campaign_gate", "status": "complete" if gate_passed else "blocked", "notes": gate_problems},
        {"stage": "research_reports", "status": "complete" if _count_files(folder / "research", "*.json") else "pending", "count": _count_files(folder / "research", "*.json")},
        {"stage": "captured_sources", "status": "complete" if source_events and not source_error else "blocked" if source_error else "pending", "count": len(source_events), "error": source_error},
        {"stage": "claim_review", "status": "complete" if claims_created and claims_assessed >= claims_created and not claim_error else "blocked" if claim_error else "pending", "created": claims_created, "assessed": claims_assessed, "events": event_counts(claim_events), "error": claim_error},
        {"stage": "script_drafts", "status": "complete" if _count_files(folder / "drafts", "*.json") else "pending", "count": _count_files(folder / "drafts", "*.json")},
        {"stage": "script_approval", "status": "complete" if scripts_registered and scripts_approved else "pending", "registered": scripts_registered, "approved_decisions": scripts_approved, "events": event_counts(script_events), "error": script_error},
        {"stage": "media_candidates", "status": "complete" if candidates and not candidate_error else "blocked" if candidate_error else "pending", "count": len(candidates), "error": candidate_error},
        {"stage": "media_rights_review", "status": "complete" if media_approved else "pending", "approved_decisions": media_approved, "events": event_counts(media_events), "error": media_error},
        {"stage": "visual_plans", "status": "complete" if _count_files(folder / "visual_plans", "*.json") else "pending", "count": _count_files(folder / "visual_plans", "*.json")},
        {"stage": "editable_timelines", "status": "complete" if _count_files(folder / "timelines", "timeline_*.json") else "pending", "count": _count_files(folder / "timelines", "timeline_*.json")},
        {"stage": "final_render_registration", "status": "complete" if artifact_registered else "pending", "registered": artifact_registered},
        {"stage": "technical_qc", "status": "complete" if artifact_qc else "pending", "passed_records": artifact_qc},
        {"stage": "central_qc", "status": "complete" if central_qc_ready else "pending", "ready_records": central_qc_ready},
        {"stage": "human_artifact_approval", "status": "complete" if artifact_approved else "pending", "approved_decisions": artifact_approved},
    ]
    completed = sum(1 for stage in stages if stage["status"] == "complete")
    return {
        "project_id": project_id,
        "campaign_id": campaign_id,
        "campaign_gate_passed": gate_passed,
        "checkpoint_count": len(stages),
        "completed_checkpoints": completed,
        "progress_ratio": round(completed / len(stages), 3),
        "stages": stages,
        "note": "Checkpoint presence/status only; this report does not certify factual accuracy, copyright, media quality, approval freshness, or publish readiness.",
    }
