"""Read-only audit of interrupted Money-Geta job sessions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ACTIVE_STAGES = {"recording", "analyzing", "downloading", "rendering"}
FAILED_STAGES = {
    "recording_failed", "analysis_failed", "download_failed", "render_failed",
    "technical_qc_failed", "artifact_registration_failed",
}
REVIEW_STAGES = {"rendered_pending_human_review"}
COMPLETED_STAGES = {"recorded", "analyzed", "source_ready", "clip_ready"}


def audit_sessions(root: str | Path, *, limit: int = 100) -> dict[str, Any]:
    """Read session manifests without modifying jobs or attempting automatic resume."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ValueError("Session audit limit must be between 1 and 500.")
    base = Path(root).expanduser()
    if base.is_symlink():
        raise ValueError("Jobs root cannot be a symlink.")
    base = base.resolve()
    if not base.is_dir():
        return {"jobs_root": str(base), "count": 0, "sessions": [], "note": "jobs root missing"}
    entries: list[dict[str, Any]] = []
    for manifest in sorted(base.rglob("money-geta.json"), key=lambda p: p.as_posix()):
        if len(entries) >= limit:
            break
        if manifest.is_symlink():
            entries.append({"manifest": str(manifest), "status": "blocked", "reason": "symlink manifest blocked"})
            continue
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            entries.append({"manifest": str(manifest), "status": "blocked", "reason": "manifest malformed or unreadable"})
            continue
        if not isinstance(payload, dict):
            entries.append({"manifest": str(manifest), "status": "blocked", "reason": "manifest is not a JSON object"})
            continue
        schema_version = payload.get("schema_version", 1)  # legacy manifests are schema v1
        if schema_version != 1 or isinstance(schema_version, bool):
            entries.append({"manifest": str(manifest), "status": "blocked", "reason": f"unsupported session schema_version: {schema_version}"})
            continue
        stage = payload.get("stage")
        if not isinstance(stage, str) or not stage:
            entries.append({"manifest": str(manifest), "status": "blocked", "reason": "session stage is missing or invalid"})
            continue
        job_id = payload.get("job_id")
        if job_id is not None and not isinstance(job_id, str):
            entries.append({"manifest": str(manifest), "status": "blocked", "reason": "job_id must be a string"})
            continue
        if stage in ACTIVE_STAGES or stage == "created":
            status = "interrupted_or_active"
            recommendation = "Inspect the session manifest and output files; resume manually only after verifying inputs."
        elif stage in FAILED_STAGES:
            status = "failed"
            recommendation = "Inspect failure details and preserve existing outputs before retrying."
        elif stage in REVIEW_STAGES:
            status = "human_review_pending"
            recommendation = "Review the rendered output; do not publish automatically."
        elif stage in COMPLETED_STAGES:
            status = "completed_stage"
            recommendation = "No automatic action required."
        else:
            status = "unknown_stage"
            recommendation = "Inspect this manifest manually; stage is not recognized by this audit."
        entries.append({
            "manifest": str(manifest),
            "job_id": job_id,
            "stage": stage,
            "status": status,
            "updated_at": payload.get("updated_at"),
            "recommendation": recommendation,
        })
    return {
        "jobs_root": str(base),
        "count": len(entries),
        "sessions": entries,
        "note": "Read-only audit. No job is resumed, restarted, deleted, or changed.",
    }
