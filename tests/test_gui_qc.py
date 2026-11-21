import json

from scripts.artifact_registry import register_artifact
from scripts.gui_qc import discover_registered_artifacts, run_registered_artifact_qc


def _registered_video(tmp_path):
    campaign_dir = tmp_path / "projects" / "project-a" / "campaigns" / "campaign-a"
    campaign_dir.mkdir(parents=True)
    campaign = campaign_dir / "campaign.json"
    campaign.write_text(json.dumps({"schema_version": 1, "project_id": "project-a", "campaign_id": "campaign-a"}), encoding="utf-8")
    video_dir = tmp_path / "mpt" / "storage" / "tasks"
    video_dir.mkdir(parents=True)
    video = video_dir / "video.mp4"
    video.write_bytes(b"fake video data")
    item = register_artifact(campaign, video, allowed_root=video_dir, metadata={"format": "9:16", "engine": "MPT"})
    return campaign, video, item


def test_discovery_returns_registered_outputs_and_skips_invalid_entries(tmp_path):
    campaign, video, item = _registered_video(tmp_path)
    records, errors = discover_registered_artifacts(tmp_path / "projects")
    assert errors == []
    assert len(records) == 1
    assert records[0]["artifact_id"] == item["artifact_id"]
    assert records[0]["path"] == str(video.resolve())
    assert records[0]["campaign_path"] == str(campaign.resolve())


def test_run_registered_qc_writes_hash_bound_reports_and_records_ready(monkeypatch, tmp_path):
    campaign, video, item = _registered_video(tmp_path)
    import scripts.artifact_registry as registry
    import scripts.perceptual_qc as perceptual

    monkeypatch.setattr(registry, "run_artifact_qc", lambda campaign, artifact_id, sha256, **kwargs: {
        "passed": True, "problems": [], "probe": {"format": "mp4"}, "sha256": sha256,
    })
    monkeypatch.setattr(perceptual, "analyze", lambda video: {
        "schema_version": 1, "file": str(video), "sha256": item["sha256"],
        "observations": {"black_segments": [], "freeze_segments": [], "silence_segments_ended": []},
    })
    result = run_registered_artifact_qc(campaign, item["artifact_id"], item["sha256"])
    assert result["central"]["status"] == "READY_FOR_HUMAN_REVIEW"
    assert result["central_event"]["sha256"] == item["sha256"]
    assert json.loads(Path(result["central_path"]).read_text(encoding="utf-8"))["status"] == "READY_FOR_HUMAN_REVIEW"
    stored = registry.list_artifacts(campaign)[0]
    assert stored["latest_central_qc"]["status"] == "READY_FOR_HUMAN_REVIEW"


def test_perceptual_execution_error_fails_closed(monkeypatch, tmp_path):
    campaign, video, item = _registered_video(tmp_path)
    import scripts.artifact_registry as registry
    import scripts.perceptual_qc as perceptual

    monkeypatch.setattr(registry, "run_artifact_qc", lambda campaign, artifact_id, sha256, **kwargs: {
        "passed": True, "problems": [], "probe": {},
    })
    def fail_analysis(_video):
        raise RuntimeError("ffmpeg unavailable")
    monkeypatch.setattr(perceptual, "analyze", fail_analysis)
    result = run_registered_artifact_qc(campaign, item["artifact_id"], item["sha256"])
    assert result["central"]["status"] == "FAILED"
    assert "Perceptual QC failed" in result["central"]["blocking"][0]
    assert registry.list_artifacts(campaign)[0]["latest_central_qc"]["status"] == "FAILED"
