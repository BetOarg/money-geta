"""Consolidate separate technical/subtitle/perceptual QC reports into a review status."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_report(report_path: Path, artifact: Path) -> dict[str, Any]:
    data = json.loads(report_path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"QC report must be a JSON object: {report_path}")
    reported_file = data.get("file")
    if not isinstance(reported_file, str) or Path(reported_file).expanduser().resolve() != artifact.resolve():
        raise ValueError(f"QC report file path does not match target artifact: {report_path}")
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported QC report schema: {report_path}")
    return data


def evaluate(artifact_path: Path, *, technical_report: Path | None,
            subtitle_report: Path | None = None, subtitle_required: bool = False,
            perceptual_report: Path | None = None) -> dict[str, Any]:
    artifact = artifact_path.expanduser().resolve(strict=True)
    if not artifact.is_file():
        raise ValueError("Artifact must be a regular file")
    artifact_hash = sha256(artifact)
    blocking: list[str] = []
    review: list[str] = []
    checks: dict[str, Any] = {}

    if technical_report is None:
        blocking.append("Technical QC report is required")
    else:
        technical = _load_report(technical_report, artifact)
        checks["technical"] = {"passed": bool(technical.get("passed")), "problems": technical.get("problems", [])}
        if technical.get("passed") is not True:
            blocking.append("Technical QC did not pass")

    if subtitle_report is None:
        checks["subtitles"] = {"status": "not_provided"}
        if subtitle_required:
            blocking.append("Subtitle QC report is required but missing")
    else:
        subtitles = _load_report(subtitle_report, artifact)
        checks["subtitles"] = {"passed": bool(subtitles.get("passed")), "problems": subtitles.get("problems", []), "cue_count": subtitles.get("cue_count")}
        if subtitles.get("passed") is not True:
            if subtitle_required:
                blocking.append("Subtitle QC did not pass")
            else:
                review.append("Subtitle QC has findings; review them before approval")

    if perceptual_report is None:
        checks["perceptual"] = {"status": "not_provided"}
    else:
        perceptual = _load_report(perceptual_report, artifact)
        observations = perceptual.get("observations", {})
        if not isinstance(observations, dict):
            raise ValueError("Perceptual report observations must be an object")
        findings = {k: v for k, v in observations.items() if v}
        checks["perceptual"] = {"observations": findings}
        if findings:
            review.append("Perceptual observations require human review; they are not automatic defects")

    if blocking:
        status = "FAILED"
    elif review:
        status = "REVIEW_REQUIRED"
    else:
        status = "READY_FOR_HUMAN_REVIEW"
    return {"schema_version": 1, "artifact": str(artifact), "sha256": artifact_hash,
            "status": status, "blocking": blocking, "review": review, "checks": checks,
            "note": "This report does not approve, publish, or schedule. Human review and rights/platform checks remain mandatory."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="Final video artifact")
    parser.add_argument("--technical-report", type=Path, required=True, help="FFprobe QC JSON")
    parser.add_argument("--subtitle-report", type=Path, help="Subtitle QC JSON")
    parser.add_argument("--subtitle-required", action="store_true")
    parser.add_argument("--perceptual-report", type=Path, help="Observational perceptual QC JSON")
    parser.add_argument("--report", type=Path, help="Write consolidated JSON report")
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.file, technical_report=args.technical_report,
            subtitle_report=args.subtitle_report, subtitle_required=args.subtitle_required,
            perceptual_report=args.perceptual_report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema_version": 1, "status": "FAILED", "blocking": [str(exc)]}, indent=2))
        return 2
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.report:
        destination = args.report.expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output + "\n", encoding="utf-8")
    return 0 if result["status"] == "READY_FOR_HUMAN_REVIEW" else (1 if result["status"] == "REVIEW_REQUIRED" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
