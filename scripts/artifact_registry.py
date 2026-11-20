"""Hash-bound final video artifact registration and human approval ledger."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ArtifactReviewError(ValueError):
    """Artifact records, file paths or approvals are invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _campaign_context(campaign_path: str | Path) -> tuple[Path, dict[str, Any], Path]:
    supplied = Path(campaign_path).expanduser()
    _reject_symlink_components(supplied)
    if supplied.is_symlink():
        raise ArtifactReviewError("Campaign manifest symlinks are blocked.")
    path = supplied.resolve(strict=True)
    if not path.is_file() or path.name != "campaign.json":
        raise ArtifactReviewError("A regular campaign.json manifest is required.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ArtifactReviewError("Campaign manifest is unreadable or malformed.") from None
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ArtifactReviewError("Unsupported campaign manifest.")
    for key in ("project_id", "campaign_id"):
        value = data.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", value):
            raise ArtifactReviewError(f"Campaign has an invalid {key}.")
    ledger = path.parent / "artifact_ledger.jsonl"
    if ledger.is_symlink():
        raise ArtifactReviewError("Artifact ledger symlinks are blocked.")
    return path, data, ledger


def _reject_symlink_components(path: Path) -> None:
    expanded = path.expanduser()
    absolute = expanded if expanded.is_absolute() else Path.cwd() / expanded
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        if part in {"", "."}:
            continue
        if part == "..":
            current = current.parent
            continue
        current = current / part
        if current.is_symlink():
            raise ArtifactReviewError("Symlink paths are blocked for reviewed artifacts.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise ArtifactReviewError("Artifact cannot be read for hashing.") from None
    return digest.hexdigest()


def _read_events(ledger: Path) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    if ledger.is_symlink() or not ledger.is_file():
        raise ArtifactReviewError("Artifact ledger is not a regular file.")
    try:
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ArtifactReviewError("Artifact ledger is malformed.") from None
    if any(not isinstance(row, dict) or row.get("schema_version") != 1 for row in rows):
        raise ArtifactReviewError("Artifact ledger contains an unsupported event.")
    seen: set[str] = set()
    registered_hashes: dict[str, str] = {}
    for row in rows:
        event = row.get("event_type")
        artifact_id = row.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ArtifactReviewError("Artifact ledger event has no artifact_id.")
        if event == "artifact_registered":
            if artifact_id in seen or not re.fullmatch(r"[0-9a-f]{32}", artifact_id):
                raise ArtifactReviewError("Artifact registration history is inconsistent.")
            seen.add(artifact_id)
            if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", ""))):
                raise ArtifactReviewError("Artifact registration has an invalid SHA-256.")
            registered_hashes[artifact_id] = row["sha256"]
        elif event in {"artifact_approved", "artifact_rejected"}:
            if (artifact_id not in seen or row.get("sha256") != registered_hashes.get(artifact_id)
                    or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", "")))):
                raise ArtifactReviewError("Artifact decision is malformed or precedes registration.")
            if not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip():
                raise ArtifactReviewError("Artifact decision is missing its reviewer.")
        else:
            raise ArtifactReviewError("Artifact ledger contains an unknown event type.")
    return rows


def _append(ledger: Path, event: dict[str, Any]) -> None:
    if ledger.is_symlink():
        raise ArtifactReviewError("Artifact ledger symlinks are blocked.")
    try:
        with ledger.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        raise ArtifactReviewError("Could not append to artifact ledger.") from None


def register_artifact(campaign_path: str | Path, artifact_path: str | Path, *,
                      allowed_root: str | Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Register a rendered MP4. The artifact must be directly inside an explicit allowed root."""
    _, campaign, ledger = _campaign_context(campaign_path)
    supplied = Path(artifact_path).expanduser()
    root_supplied = Path(allowed_root).expanduser()
    _reject_symlink_components(supplied)
    _reject_symlink_components(root_supplied)
    path = supplied.resolve(strict=True)
    root = root_supplied.resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError:
        raise ArtifactReviewError("Artifact must remain inside the allowed output directory.") from None
    if not root.is_dir() or path == root or not path.is_file() or path.suffix.lower() != ".mp4":
        raise ArtifactReviewError("Artifact must be a regular MP4 inside the allowed output directory.")
    if path.is_symlink() or root.is_symlink():
        raise ArtifactReviewError("Symlink paths are blocked for reviewed artifacts.")
    rows = _read_events(ledger)
    artifact_id = uuid.uuid4().hex
    info = {
        "schema_version": 1, "event_type": "artifact_registered",
        "artifact_id": artifact_id, "project_id": campaign["project_id"],
        "campaign_id": campaign["campaign_id"], "path": str(path),
        "allowed_root": str(root), "file_size": path.stat().st_size,
        "sha256": _sha256(path), "engine": (metadata or {}).get("engine", "unknown"),
        "format": (metadata or {}).get("format", "unknown"),
        "subject": (metadata or {}).get("subject", ""),
        "language": (metadata or {}).get("language", ""),
        "count": (metadata or {}).get("count"),
        "voice": (metadata or {}).get("voice"),
        "session_id": (metadata or {}).get("session_id"),
        "task_id": (metadata or {}).get("task_id"),
        "registered_at": _now(),
    }
    _append(ledger, info)
    return info


def list_artifacts(campaign_path: str | Path) -> list[dict[str, Any]]:
    _, _, ledger = _campaign_context(campaign_path)
    rows = _read_events(ledger)
    registrations = {row["artifact_id"]: dict(row) for row in rows if row["event_type"] == "artifact_registered"}
    for row in rows:
        if row["event_type"] in {"artifact_approved", "artifact_rejected"}:
            registrations[row["artifact_id"]]["latest_decision"] = row
    return list(registrations.values())


def approve_artifact(campaign_path: str | Path, artifact_id: str, sha256: str, *,
                     reviewer: str, decision: str = "approved", notes: str = "") -> dict[str, Any]:
    _, _, ledger = _campaign_context(campaign_path)
    if decision not in {"approved", "rejected"}:
        raise ArtifactReviewError("Decision must be approved or rejected.")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
        raise ArtifactReviewError("A reviewer name of 1 to 120 characters is required.")
    if len(notes) > 2000:
        raise ArtifactReviewError("Review notes cannot exceed 2000 characters.")
    if not re.fullmatch(r"[0-9a-f]{32}", artifact_id) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ArtifactReviewError("A valid artifact ID and exact SHA-256 are required.")
    rows = _read_events(ledger)
    registration = next((row for row in rows if row["event_type"] == "artifact_registered"
                         and row["artifact_id"] == artifact_id), None)
    if registration is None:
        raise ArtifactReviewError("Unknown artifact ID.")
    if registration["sha256"] != sha256:
        raise ArtifactReviewError("Provided SHA-256 does not match the registered artifact.")
    path = Path(registration["path"])
    root = Path(registration["allowed_root"])
    _reject_symlink_components(path)
    _reject_symlink_components(root)
    try:
        path.relative_to(root)
    except ValueError:
        raise ArtifactReviewError("Artifact moved outside its allowed output directory.") from None
    if not path.is_file() or path.is_symlink() or _sha256(path) != sha256:
        raise ArtifactReviewError("Artifact is missing, moved or changed since registration.")
    event = {
        "schema_version": 1, "event_type": "artifact_approved" if decision == "approved" else "artifact_rejected",
        "artifact_id": artifact_id, "sha256": sha256, "reviewer": reviewer.strip(),
        "notes": notes.strip(), "decided_at": _now(),
    }
    _append(ledger, event)
    return event


def check_artifact(campaign_path: str | Path, artifact_id: str, sha256: str) -> tuple[bool, list[str]]:
    rows = _read_events(_campaign_context(campaign_path)[2])
    registration = next((row for row in rows if row["event_type"] == "artifact_registered"
                         and row["artifact_id"] == artifact_id), None)
    if registration is None:
        return False, ["artifact is not registered for this campaign"]
    if registration.get("sha256") != sha256:
        return False, ["requested SHA-256 does not match registered artifact"]
    path, root = Path(registration["path"]), Path(registration["allowed_root"])
    try:
        _reject_symlink_components(path)
        _reject_symlink_components(root)
        try:
            path.relative_to(root)
        except ValueError:
            return False, ["artifact moved outside its allowed output directory"]
        if not path.is_file() or path.is_symlink() or _sha256(path) != sha256:
            return False, ["artifact is missing or its contents changed after registration"]
    except (OSError, ArtifactReviewError):
        return False, ["artifact path is no longer safe or accessible"]
    decisions = [row for row in rows if row["artifact_id"] == artifact_id
                 and row["event_type"] in {"artifact_approved", "artifact_rejected"}]
    if not decisions:
        return False, ["artifact has not received human approval"]
    latest = decisions[-1]
    if latest["sha256"] != sha256 or latest["event_type"] != "artifact_approved":
        return False, ["latest human decision does not approve this exact artifact hash"]
    return True, []


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Review final Money-Geta MP4 artifacts by exact SHA-256.")
    parser.add_argument("--campaign", type=Path, required=True, help="campaign.json manifest")
    sub = parser.add_subparsers(dest="action", required=True)
    listing = sub.add_parser("list", help="list registered final artifacts")
    approve = sub.add_parser("approve", help="approve or reject an exact registered artifact")
    approve.add_argument("--artifact-id", required=True)
    approve.add_argument("--sha256", required=True)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--decision", choices=["approved", "rejected"], default="approved")
    approve.add_argument("--notes", default="")
    check = sub.add_parser("check", help="check whether an exact artifact is approved and unchanged")
    check.add_argument("--artifact-id", required=True)
    check.add_argument("--sha256", required=True)
    publication = sub.add_parser("publication-check", help="combine campaign readiness and exact artifact approval")
    publication.add_argument("--artifact-id", required=True)
    publication.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "list":
            for item in list_artifacts(args.campaign):
                decision = item.get("latest_decision", {}).get("event_type", "pending")
                print(f'{item["artifact_id"]} | {item["sha256"]} | {decision} | {item["path"]}')
            return 0
        if args.action == "approve":
            result = approve_artifact(args.campaign, args.artifact_id, args.sha256,
                                      reviewer=args.reviewer, decision=args.decision, notes=args.notes)
            print(f'{result["event_type"]}: {result["artifact_id"]} sha256={result["sha256"]}')
            return 0
        passed, problems = check_artifact(args.campaign, args.artifact_id, args.sha256)
        if args.action == "publication-check":
            from scripts.campaign_check import check_file
            campaign_passed, campaign_problems = check_file(args.campaign)
            if not campaign_passed:
                problems = [f"campaign: {item}" for item in campaign_problems] + problems
                passed = False
        if not passed:
            print("PUBLICATION CHECK: BLOCKED")
            for problem in problems:
                print(f"- {problem}")
            return 2
        print("PUBLICATION CHECK: READY_FOR_HUMAN_PUBLISH_ACTION" if args.action == "publication-check" else "ARTIFACT CHECK: APPROVED")
        print("No content is published by this command. Human publication authorization and platform-specific checks remain separate.")
        return 0
    except (ArtifactReviewError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
