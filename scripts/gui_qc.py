"""Desktop GUI helpers for artifact discovery and hash-bound quality review."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def discover_registered_artifacts(*roots: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Find registered final videos under campaign manifests, without following symlink manifests."""
    from scripts.artifact_registry import list_artifacts

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    manifests: set[Path] = set()
    for root in roots:
        root = root.expanduser()
        if not root.is_dir() or root.is_symlink():
            continue
        try:
            manifests.update(path for path in root.rglob("campaign.json") if path.is_file() and not path.is_symlink())
        except OSError as exc:
            errors.append(f"Campaign scan failed in {root}: {exc}")
    for campaign in sorted(manifests):
        try:
            for item in list_artifacts(campaign):
                record = dict(item)
                record["campaign_path"] = str(campaign.resolve())
                video = Path(str(record.get("path", "")))
                if not video.is_file() or video.is_symlink():
                    continue
                records.append(record)
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"Could not list artifacts for {campaign}: {exc}")
    records.sort(key=lambda item: str(item.get("registered_at", "")), reverse=True)
    return records, errors


def _write_report(directory: Path, name: str, payload: dict[str, Any]) -> Path:
    from scripts.artifact_registry import _reject_symlink_components

    _reject_symlink_components(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("QC report directory symlinks are blocked.")
    target = directory / name
    _reject_symlink_components(target)
    temporary = target.with_suffix(target.suffix + ".tmp")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(serialized + "\\n")
    temporary.replace(target)
    return target


def run_registered_artifact_qc(campaign_path: Path, artifact_id: str, sha256: str,
                              *, subtitle_path: Path | None = None) -> dict[str, Any]:
    """Run technical, perceptual and optional subtitle QC; bind central result to the exact MP4."""
    from scripts.artifact_registry import list_artifacts, record_central_qc, run_artifact_qc
    from scripts.perceptual_qc import analyze
    from scripts.qc_orchestrator import evaluate
    from scripts.quality_control import inspect_media
    from scripts.subtitle_quality import inspect_subtitles

    campaign = campaign_path.expanduser().resolve(strict=True)
    item = next((row for row in list_artifacts(campaign)
                 if row.get("artifact_id") == artifact_id), None)
    if not item or item.get("sha256") != sha256:
        raise ValueError("Selected artifact ID/hash is not registered for this campaign.")
    video = Path(item["path"]).resolve(strict=True)
    if not video.is_file():
        raise ValueError("Selected artifact is not a regular video file.")
    report_dir = campaign.parent / "qc_reports"
    token = sha256[:12]
    technical_path = report_dir / f"{artifact_id}-{token}-technical.json"
    perceptual_path = report_dir / f"{artifact_id}-{token}-perceptual.json"
    subtitle_report_path = None
    central_path = report_dir / f"{artifact_id}-{token}-central.json"

    technical = inspect_media(video, expected_aspect=item.get("format"))
    technical["file"] = str(video)
    technical["sha256"] = sha256
    technical_path = _write_report(report_dir, technical_path.name, technical)
    technical_event = run_artifact_qc(campaign, artifact_id, sha256, expected_aspect=item.get("format"))

    perceptual_error = None
    try:
        perceptual = analyze(video)
        perceptual["file"] = str(video)
        perceptual["sha256"] = sha256
        perceptual_path = _write_report(report_dir, perceptual_path.name, perceptual)
    except (OSError, RuntimeError, ValueError) as exc:
        perceptual_error = str(exc)
        perceptual = None

    subtitle = None
    if subtitle_path is not None:
        subtitle = inspect_subtitles(subtitle_path.expanduser().resolve())
        subtitle_report_path = _write_report(
            report_dir, f"{artifact_id}-{token}-subtitle-{subtitle.get('sha256', 'unknown')[:12]}.json", subtitle
        )

    if perceptual is None:
        central = {
            "schema_version": 1, "artifact": str(video), "sha256": sha256,
            "status": "FAILED", "blocking": [f"Perceptual QC failed: {perceptual_error}"],
            "review": [], "checks": {"technical": {"passed": technical.get("passed") is True}},
            "note": "Fail-closed: perceptual QC execution error prevents human-review readiness.",
        }
    else:
        central = evaluate(
            video, technical_report=technical_path, subtitle_report=subtitle_report_path,
            subtitle_required=False, perceptual_report=perceptual_path, perceptual_required=True,
        )
    central_path = _write_report(report_dir, central_path.name, central)
    central_event = record_central_qc(campaign, artifact_id, sha256, central_path)
    return {
        "artifact": item, "technical": technical, "technical_event": technical_event,
        "perceptual": perceptual, "perceptual_error": perceptual_error,
        "subtitle": subtitle, "central": central, "central_path": str(central_path),
        "central_event": central_event,
    }
