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
        elif event in {"artifact_approved", "artifact_rejected", "artifact_qc", "artifact_central_qc"}:
            if (artifact_id not in seen or row.get("sha256") != registered_hashes.get(artifact_id)
                    or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", "")))):
                raise ArtifactReviewError("Artifact decision/QC is malformed or precedes registration.")
            if event in {"artifact_approved", "artifact_rejected"}:
                if not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip():
                    raise ArtifactReviewError("Artifact decision is missing its reviewer.")
            elif event == "artifact_qc":
                if (not isinstance(row.get("passed"), bool) or not isinstance(row.get("problems"), list)
                        or any(not isinstance(item, str) for item in row.get("problems", []))
                        or not isinstance(row.get("probe", {}), dict)):
                    raise ArtifactReviewError("Artifact QC event is malformed.")
            elif event == "artifact_central_qc":
                if row.get("status") not in {"FAILED", "REVIEW_REQUIRED", "READY_FOR_HUMAN_REVIEW"} or not isinstance(row.get("report"), dict):
                    raise ArtifactReviewError("Central QC event is malformed.")
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
        elif row["event_type"] == "artifact_qc":
            registrations[row["artifact_id"]]["latest_qc"] = row
        elif row["event_type"] == "artifact_central_qc":
            registrations[row["artifact_id"]]["latest_central_qc"] = row
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


def run_artifact_qc(campaign_path: str | Path, artifact_id: str, sha256: str, *,
                     ffprobe: str | None = None, timeout: int = 30,
                     min_duration: float = 1.0, max_duration: float | None = None,
                     expected_aspect: str | None = None, require_audio: bool = False) -> dict[str, Any]:
    """Run technical QC and append a result bound to the registered artifact hash."""
    from scripts.quality_control import inspect_media
    rows = _read_events(_campaign_context(campaign_path)[2])
    registration = next((row for row in rows if row["event_type"] == "artifact_registered"
                        and row["artifact_id"] == artifact_id), None)
    if not registration or registration.get("sha256") != sha256:
        raise ArtifactReviewError("Artifact ID/hash does not match registration.")
    path, root = Path(registration["path"]), Path(registration["allowed_root"])
    _reject_symlink_components(path)
    _reject_symlink_components(root)
    try:
        path.relative_to(root)
    except ValueError:
        raise ArtifactReviewError("Artifact moved outside its allowed output directory.") from None
    if not path.is_file() or path.is_symlink() or _sha256(path) != sha256:
        raise ArtifactReviewError("Artifact is missing or changed since registration.")
    try:
        report = inspect_media(path, ffprobe=ffprobe, timeout=timeout,
            min_duration=min_duration, max_duration=max_duration,
            expected_aspect=expected_aspect, require_audio=require_audio)
    except (OSError, ValueError) as exc:
        report = {"passed": False, "problems": [str(exc)]}
    event = {"schema_version": 1, "event_type": "artifact_qc", "artifact_id": artifact_id,
        "sha256": sha256, "passed": bool(report.get("passed")),
        "problems": report.get("problems", []), "probe": report.get("probe", {}),
        "qc_at": _now()}
    _append(_campaign_context(campaign_path)[2], event)
    return event


def record_central_qc(campaign_path: str | Path, artifact_id: str, sha256: str, report_path: str | Path) -> dict[str, Any]:
    """Record consolidated QC only when its exact hash matches the registered MP4."""
    _, _, ledger = _campaign_context(campaign_path)
    rows = _read_events(ledger)
    registration = next((row for row in rows if row["event_type"] == "artifact_registered" and row["artifact_id"] == artifact_id), None)
    if not registration or registration.get("sha256") != sha256:
        raise ArtifactReviewError("Artifact ID/hash does not match registration.")
    path, root = Path(registration["path"]), Path(registration["allowed_root"])
    _reject_symlink_components(path); _reject_symlink_components(root)
    try: path.relative_to(root)
    except ValueError: raise ArtifactReviewError("Artifact moved outside allowed output directory.") from None
    if not path.is_file() or path.is_symlink() or _sha256(path) != sha256:
        raise ArtifactReviewError("Artifact missing or changed after registration.")
    report_supplied = Path(report_path).expanduser()
    _reject_symlink_components(report_supplied)
    if report_supplied.is_symlink():
        raise ArtifactReviewError("QC report symlinks are blocked.")
    report_file = report_supplied.resolve(strict=True)
    if not report_file.is_file():
        raise ArtifactReviewError("QC report must be a regular file.")
    try: report = json.loads(report_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError): raise ArtifactReviewError("QC report is malformed.") from None
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ArtifactReviewError("Unsupported central QC report schema.")
    if Path(str(report.get("artifact", ""))).expanduser().resolve() != path:
        raise ArtifactReviewError("Central QC report points to a different artifact.")
    if report.get("sha256") != sha256:
        raise ArtifactReviewError("Central QC report hash does not match registered artifact.")
    status = report.get("status")
    if status not in {"FAILED", "REVIEW_REQUIRED", "READY_FOR_HUMAN_REVIEW"}:
        raise ArtifactReviewError("Central QC status invalid.")
    blocking = report.get("blocking")
    review = report.get("review")
    if (not isinstance(blocking, list) or any(not isinstance(x, str) for x in blocking)
            or not isinstance(review, list) or any(not isinstance(x, str) for x in review)):
        raise ArtifactReviewError("Central QC blocking/review lists are malformed.")
    if status == "READY_FOR_HUMAN_REVIEW" and (blocking or review):
        raise ArtifactReviewError("READY central QC cannot contain blocking issues or review findings.")
    if status == "FAILED" and not blocking:
        raise ArtifactReviewError("FAILED central QC must include blocking issues.")
    if status == "REVIEW_REQUIRED" and not review:
        raise ArtifactReviewError("REVIEW_REQUIRED central QC must include review findings.")
    event = {"schema_version": 1, "event_type": "artifact_central_qc", "artifact_id": artifact_id,
              "sha256": sha256, "status": status, "report": report, "qc_at": _now()}
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
    central = sub.add_parser("central-qc-record", help="record a consolidated hash-bound QC report")
    central.add_argument("--artifact-id", required=True)
    central.add_argument("--sha256", required=True)
    central.add_argument("--report", type=Path, required=True)
    qc = sub.add_parser("qc", help="run technical QC and record it against an exact artifact hash")
    qc.add_argument("--artifact-id", required=True)
    qc.add_argument("--sha256", required=True)
    qc.add_argument("--ffprobe")
    qc.add_argument("--timeout", type=int, default=30)
    qc.add_argument("--min-duration", type=float, default=1.0)
    qc.add_argument("--max-duration", type=float)
    qc.add_argument("--aspect", choices=("9:16", "16:9", "1:1"))
    qc.add_argument("--require-audio", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "list":
            for item in list_artifacts(args.campaign):
                decision = item.get("latest_decision", {}).get("event_type", "pending")
                qc_status = item.get("latest_central_qc", {}).get("status", "central-qc-pending")
                print(f'{item["artifact_id"]} | {item["sha256"]} | {decision} | {qc_status} | {item["path"]}')
            return 0
        if args.action == "approve":
            result = approve_artifact(args.campaign, args.artifact_id, args.sha256,
                                      reviewer=args.reviewer, decision=args.decision, notes=args.notes)
            print(f'{result["event_type"]}: {result["artifact_id"]} sha256={result["sha256"]}')
            return 0
        if args.action == "central-qc-record":
            event = record_central_qc(args.campaign, args.artifact_id, args.sha256, args.report)
            print(f'CENTRAL QC RECORDED: {event["status"]} artifact={event["artifact_id"]} sha256={event["sha256"]}')
            return 0 if event["status"] == "READY_FOR_HUMAN_REVIEW" else 2
        if args.action == "qc":
            result = run_artifact_qc(args.campaign, args.artifact_id, args.sha256,
                ffprobe=args.ffprobe, timeout=args.timeout, min_duration=args.min_duration,
                max_duration=args.max_duration, expected_aspect=args.aspect, require_audio=args.require_audio)
            print("QC: PASS" if result["passed"] else "QC: FAIL")
            for issue in result["problems"]: print(f"- {issue}")
            return 0 if result["passed"] else 2
        passed, problems = check_artifact(args.campaign, args.artifact_id, args.sha256)
        if args.action == "publication-check":
            from scripts.campaign_check import check_file
            campaign_passed, campaign_problems = check_file(args.campaign)
            all_events = _read_events(_campaign_context(args.campaign)[2])
            qc_events = [row for row in all_events if row.get("event_type") == "artifact_qc" and row.get("artifact_id") == args.artifact_id]
            if not qc_events:
                problems.append("technical QC has not been recorded for this artifact")
                passed = False
            else:
                latest_qc = qc_events[-1]
                if latest_qc.get("sha256") != args.sha256 or not latest_qc.get("passed"):
                    problems.append("latest technical QC does not pass for this exact artifact hash")
                    passed = False
            central_events = [(i,row) for i,row in enumerate(all_events) if row.get("event_type") == "artifact_central_qc" and row.get("artifact_id") == args.artifact_id]
            if not central_events:
                problems.append("central QC has not been recorded for this artifact")
                passed = False
            else:
                central_index, central_latest = central_events[-1]
                if central_latest.get("sha256") != args.sha256 or central_latest.get("status") != "READY_FOR_HUMAN_REVIEW":
                    problems.append("latest central QC is not READY_FOR_HUMAN_REVIEW for this exact hash")
                    passed = False
                approval_indices = [i for i,row in enumerate(all_events) if row.get("event_type") == "artifact_approved" and row.get("artifact_id") == args.artifact_id and row.get("sha256") == args.sha256]
                if not approval_indices or approval_indices[-1] <= central_index:
                    problems.append("human approval must be recorded after the latest central QC")
                    passed = False
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
