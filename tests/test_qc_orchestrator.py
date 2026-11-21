import json
from pathlib import Path

import pytest

from scripts.qc_orchestrator import evaluate


def write_report(path, target, data):
    data["file"] = str(target.resolve())
    path.write_text(json.dumps(data), encoding="utf-8")


def test_ready_when_required_technical_passes_and_optional_reports_absent(tmp_path):
    artifact = tmp_path / "render.mp4"
    artifact.write_bytes(b"video")
    technical = tmp_path / "technical.json"
    write_report(technical, artifact, {"schema_version": 1, "passed": True, "problems": []})
    result = evaluate(artifact, technical_report=technical)
    assert result["status"] == "READY_FOR_HUMAN_REVIEW"
    assert result["sha256"]


def test_blocked_on_failed_technical(tmp_path):
    artifact = tmp_path / "render.mp4"
    artifact.write_bytes(b"video")
    technical = tmp_path / "technical.json"
    write_report(technical, artifact, {"schema_version": 1, "passed": False, "problems": ["no audio"]})
    result = evaluate(artifact, technical_report=technical)
    assert result["status"] == "FAILED"


def test_perceptual_findings_require_review_not_fail(tmp_path):
    artifact = tmp_path / "render.mp4"
    artifact.write_bytes(b"video")
    technical = tmp_path / "technical.json"
    perceptual = tmp_path / "perceptual.json"
    write_report(technical, artifact, {"schema_version": 1, "passed": True, "problems": []})
    write_report(perceptual, artifact, {"schema_version": 1, "observations": {"black_segments": [{"duration": 2}]}})
    result = evaluate(artifact, technical_report=technical, perceptual_report=perceptual)
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["blocking"] == []


def test_missing_required_subtitle_report_blocks(tmp_path):
    artifact = tmp_path / "render.mp4"
    artifact.write_bytes(b"video")
    technical = tmp_path / "technical.json"
    write_report(technical, artifact, {"schema_version": 1, "passed": True, "problems": []})
    result = evaluate(artifact, technical_report=technical, subtitle_required=True)
    assert result["status"] == "FAILED"


def test_wrong_report_target_rejected(tmp_path):
    artifact = tmp_path / "render.mp4"
    other = tmp_path / "other.mp4"
    artifact.write_bytes(b"video")
    other.write_bytes(b"not target")
    technical = tmp_path / "technical.json"
    write_report(technical, other, {"schema_version": 1, "passed": True, "problems": []})
    with pytest.raises(ValueError, match="does not match target"):
        evaluate(artifact, technical_report=technical)
