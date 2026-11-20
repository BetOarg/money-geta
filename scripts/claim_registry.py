"""Append-only, operator-assessed claim ledger backed by captured source evidence."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.campaign_registry import get_campaign
from scripts.project_registry import default_projects_root, get_project, safe_slug


class ClaimRegistryError(ValueError):
    """Claim/evidence records are incomplete or inconsistent."""


STATUSES = {"supported", "contradicted", "unsupported", "unverified"}


def _campaign_folder(project_id: str, campaign_id: str, root: Path | None) -> Path:
    if safe_slug(project_id) != project_id or safe_slug(campaign_id) != campaign_id:
        raise ClaimRegistryError("Project and campaign IDs must be normalized slugs.")
    base = (root or default_projects_root()).expanduser().resolve()
    get_project(project_id, base)
    get_campaign(project_id, campaign_id, base)
    folder = (base / project_id / "campaigns" / campaign_id).resolve()
    if not folder.is_relative_to(base) or not folder.is_dir():
        raise ClaimRegistryError("Campaign directory is invalid or outside projects root.")
    return folder


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise ClaimRegistryError(f"Ledger path is not a regular file: {path.name}")
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ClaimRegistryError(f"Ledger is malformed: {path.name}") from None
    if any(not isinstance(row, dict) or row.get("schema_version") != 1 for row in rows):
        raise ClaimRegistryError(f"Ledger contains an unsupported record: {path.name}")
    return rows


def _evidence_index(folder: Path) -> dict[str, dict[str, Any]]:
    rows = _read_jsonl(folder / "source_ledger.jsonl")
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        evidence_id, url = row.get("evidence_id"), row.get("final_url")
        if not isinstance(evidence_id, str) or not isinstance(url, str):
            raise ClaimRegistryError("Source ledger entry is missing evidence_id or final_url.")
        if evidence_id in index:
            raise ClaimRegistryError("Source ledger contains duplicate evidence IDs.")
        index[evidence_id] = row
    return index


def _claim_events(folder: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(folder / "claim_ledger.jsonl")
    if any(row.get("event_type") not in {"claim_created", "claim_assessed"} for row in rows):
        raise ClaimRegistryError("Claim ledger contains an unknown event type.")
    return rows


def _append(folder: Path, filename: str, record: dict[str, Any]) -> Path:
    target = folder / filename
    if target.is_symlink():
        raise ClaimRegistryError("Claim ledger symlinks are blocked.")
    try:
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            import os
            os.fsync(handle.fileno())
    except OSError:
        raise ClaimRegistryError("Could not append to claim ledger.") from None
    return target


def create_claim(project_id: str, campaign_id: str, claim: str, evidence_ids: list[str],
                 *, root: Path | None = None) -> dict[str, Any]:
    folder = _campaign_folder(project_id, campaign_id, root)
    text = claim.strip()
    if not text or len(text) > 1200:
        raise ClaimRegistryError("Claim must contain 1 to 1200 characters.")
    refs = list(dict.fromkeys(item.strip() for item in evidence_ids if isinstance(item, str) and item.strip()))
    if not refs:
        raise ClaimRegistryError("At least one captured evidence ID is required.")
    evidence = _evidence_index(folder)
    missing = [item for item in refs if item not in evidence]
    if missing:
        raise ClaimRegistryError("Unknown evidence IDs: " + ", ".join(missing))
    now = datetime.now(timezone.utc).isoformat()
    claim_id = hashlib.sha256((project_id + "\n" + campaign_id + "\n" + text + "\n" + now).encode()).hexdigest()[:20]
    record = {
        "schema_version": 1, "event_type": "claim_created", "claim_id": claim_id,
        "project_id": project_id, "campaign_id": campaign_id, "claim": text,
        "evidence_ids": refs, "status": "unverified", "created_at": now,
    }
    _append(folder, "claim_ledger.jsonl", record)
    return record


def assess_claim(project_id: str, campaign_id: str, claim_id: str, status: str, rationale: str,
                 *, independence_attested: bool = False, contradiction_summary: str = "",
                 root: Path | None = None) -> dict[str, Any]:
    folder = _campaign_folder(project_id, campaign_id, root)
    if status not in STATUSES:
        raise ClaimRegistryError("Status must be supported, contradicted, unsupported or unverified.")
    reason = rationale.strip()
    if len(reason) < 10 or len(reason) > 2000:
        raise ClaimRegistryError("Assessment rationale must contain 10 to 2000 characters.")
    events = _claim_events(folder)
    created = next((row for row in events if row.get("event_type") == "claim_created" and row.get("claim_id") == claim_id), None)
    if created is None:
        raise ClaimRegistryError("Claim ID was not found.")
    latest = next((row for row in reversed(events) if row.get("claim_id") == claim_id), created)
    if latest.get("status") in {"supported", "contradicted", "unsupported"}:
        # Re-assessment is allowed but remains append-only and must carry a fresh rationale.
        pass
    evidence = _evidence_index(folder)
    refs = created.get("evidence_ids", [])
    if any(ref not in evidence for ref in refs):
        raise ClaimRegistryError("Claim references evidence missing from the source ledger.")
    hosts = {urlsplit(evidence[ref]["final_url"]).hostname for ref in refs}
    if status == "supported":
        if len(refs) < 2 or len(hosts) < 2:
            raise ClaimRegistryError("Supported requires evidence from at least two distinct hostnames.")
        if not independence_attested:
            raise ClaimRegistryError("Supported requires explicit operator attestation of source independence.")
    if status == "contradicted":
        if len(refs) < 2 or len(hosts) < 2 or len(contradiction_summary.strip()) < 10:
            raise ClaimRegistryError("Contradicted requires two distinct hostnames and a 10+ character conflict summary.")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": 1, "event_type": "claim_assessed", "claim_id": claim_id,
        "status": status, "rationale": reason, "contradiction_summary": contradiction_summary.strip(),
        "independence_attested": bool(independence_attested), "reviewer": "operator",
        "evidence_ids": refs, "assessed_at": now,
    }
    _append(folder, "claim_ledger.jsonl", record)
    return record


def list_claims(project_id: str, campaign_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    folder = _campaign_folder(project_id, campaign_id, root)
    events = _claim_events(folder)
    claims: dict[str, dict[str, Any]] = {}
    for row in events:
        claim_id = row["claim_id"]
        if row["event_type"] == "claim_created":
            claims[claim_id] = dict(row)
        elif claim_id in claims:
            claims[claim_id]["status"] = row["status"]
            claims[claim_id]["latest_assessment"] = row
    return list(claims.values())
