"""Technical and observational QC for local timeline previews."""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from scripts.quality_control import inspect_media
from scripts.perceptual_qc import analyze


def review_preview(
    preview_path: Path,
    timeline: dict[str, Any],
    *,
    timeout: int = 120,
    report_path: Path | None = None,
    technical_checker: Callable[..., dict[str, Any]] = inspect_media,
    perceptual_checker: Callable[..., dict[str, Any]] = analyze,
) -> dict[str, Any]:
    """Check technical properties; perceptual observations are informational only."""
    if not isinstance(timeline, dict) or timeline.get("plan_type") != "editable_timeline":
        raise ValueError("An editable timeline draft is required for preview QC.")
    scenes = timeline.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Preview QC requires at least one scene.")
    total = 0.0
    for scene in scenes:
        duration = float(scene.get("duration_seconds", 0))
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Scene duration must be finite and positive.")
        total += duration
    path = Path(preview_path).expanduser().resolve()
    try:
        technical = technical_checker(path, max_duration=total, expected_aspect="9:16",
                                     require_audio=bool(timeline.get("audio_tracks")))
        technical_error = None
    except Exception as exc:
        technical = {"passed": False, "problems": [f"{type(exc).__name__}: {exc}"]}
        technical_error = f"{type(exc).__name__}: {exc}"
    try:
        perceptual = perceptual_checker(path, timeout=timeout)
        perceptual_error = None
    except Exception as exc:
        perceptual = None
        perceptual_error = f"{type(exc).__name__}: {exc}"
    report = {
        "schema_version": 1,
        "preview_file": str(path),
        "timeline_duration_seconds": round(total, 3),
        "technical": technical,
        "technical_error": technical_error,
        "perceptual_observations": perceptual,
        "perceptual_error": perceptual_error,
        "status": "PASS" if technical.get("passed") is True else "REVIEW_REQUIRED",
        "scope": "preview QC only; technical checks gate status, perceptual observations require human interpretation",
    }
    if report_path is not None:
        target = Path(report_path).expanduser().resolve()
        if target.exists():
            raise ValueError("QC report already exists; choose a new report path.")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=target.parent,
                                         prefix=".preview-qc-", suffix=".tmp") as handle:
                temp_name = handle.name
                json.dump(report, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if temp_name:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    pass
        report["report_path"] = str(target)
    return report
