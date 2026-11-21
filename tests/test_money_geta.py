from pathlib import Path

from scripts.money_geta import PATCHES, verify_patches


def test_patch_manifest_is_complete():
    assert set(PATCHES) == {"live.py"}
    for _, (_, blob, patch) in PATCHES.items():
        assert len(blob) == 40
        assert patch.is_file()


def test_upstream_check_rejects_non_git_directory(tmp_path):
    assert verify_patches(tmp_path) == 2


def test_render_invokes_mpt_cli_with_local_media_and_campaign_gate(tmp_path, monkeypatch):
    import json
    from argparse import Namespace
    from scripts import money_geta
    from scripts.artifact_registry import approve_artifact, check_artifact, list_artifacts, main as artifact_review_main
    import scripts.quality_control as quality_control
    monkeypatch.setattr(quality_control, "inspect_media", lambda *args, **kwargs: {"passed": True, "problems": [], "probe": {}})

    mpt = tmp_path / "mpt"
    mpt.mkdir()
    mpt_home = tmp_path / "mpt-runtime"
    mpt_home.mkdir()
    (mpt / "cli.py").write_text("# fake CLI", encoding="utf-8")
    (mpt_home / "config.toml").write_text("upload_post_auto_upload = false\n", encoding="utf-8")
    monkeypatch.setenv("MPT_HOME", str(mpt_home))
    python_exe = mpt / "python.exe"
    python_exe.write_text("fake interpreter", encoding="utf-8")
    from scripts.campaign_registry import create_campaign, update_campaign
    from scripts.project_registry import create_project

    projects_root = tmp_path / "projects"
    create_project("Gaming", "gaming", root=projects_root)
    campaign = create_campaign("gaming", "test", "YouTube Shorts", root=projects_root)
    update_campaign(
        "gaming", "test",
        sources=["https://example.test/source"],
        rights_evidence=["Operator-held permission evidence reference"],
        credits=["Source attribution recorded"],
        confirm_permissions=True,
        confirm_credits=True,
        root=projects_root,
    )
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not rendered; command is mocked")
    captured = {}

    class Result:
        returncode = 0
        stderr = ""

    video = mpt_home / "storage" / "tasks" / "test-task" / "final-1.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"mocked output artifact")

    calls = []
    def fake_run(command, cwd, check, **kwargs):
        calls.append(command)
        captured["command"] = command
        captured["cwd"] = cwd
        result = Result()
        result.stdout = (
            "--video-subject --video-source --video-materials --video-aspect --video-count --video-language --voice-name --stop-at"
            if command[-1] == "--help"
            else json.dumps({"task_id": "test-task", "result": {"videos": [str(video)]}})
        )
        return result

    monkeypatch.setattr(money_geta.subprocess, "run", fake_run)
    args = Namespace(
        mpt_dir=mpt, mpt_python=python_exe, campaign=campaign, materials=[media],
        subject="GTA VI test", aspect="9:16", count=1,
        language="en-US", voice=None, jobs_root=tmp_path / "jobs",
    )
    assert money_geta.run_mpt(args) == 0
    assert captured["cwd"] == mpt
    assert len(calls) == 2
    assert calls[0][-1] == "--help"
    assert str(mpt / "cli.py") in captured["command"]
    assert "--video-source" in captured["command"]
    assert captured["command"][captured["command"].index("--video-source") + 1] == "local"
    assert "--video-materials" in captured["command"]

    artifacts = list_artifacts(campaign)
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert Path(artifact["path"]).is_relative_to((mpt_home / "storage" / "tasks").resolve())
    assert Path(artifact["allowed_root"]) == (mpt_home / "storage" / "tasks").resolve()
    review_args = [
        "--campaign", str(campaign), "publication-check",
        "--artifact-id", artifact["artifact_id"], "--sha256", artifact["sha256"],
    ]
    assert check_artifact(campaign, artifact["artifact_id"], artifact["sha256"])[0] is False
    assert artifact_review_main(review_args) == 2
    central_report = Path(artifact["path"]).parent / "central-qc.json"
    central_report.write_text(json.dumps({
        "schema_version": 1, "artifact": artifact["path"], "sha256": artifact["sha256"],
        "status": "READY_FOR_HUMAN_REVIEW", "blocking": [], "review": [], "checks": {}
    }), encoding="utf-8")
    central_args = [
        "--campaign", str(campaign), "central-qc-record",
        "--artifact-id", artifact["artifact_id"], "--sha256", artifact["sha256"],
        "--report", str(central_report),
    ]
    assert artifact_review_main(central_args) == 0
    approve_artifact(campaign, artifact["artifact_id"], artifact["sha256"], reviewer="test operator")
    assert check_artifact(campaign, artifact["artifact_id"], artifact["sha256"]) == (True, [])
    assert artifact_review_main(review_args) == 0


def test_analyze_video_uses_isolated_session_and_local_source(tmp_path, monkeypatch):
    from argparse import Namespace
    from scripts import money_geta

    gtavi = tmp_path / "gtavi"
    (gtavi / "scripts").mkdir(parents=True)
    (gtavi / "scripts" / "moments.py").write_text("# mocked upstream script", encoding="utf-8")
    source = tmp_path / "vod.mp4"
    source.write_bytes(b"local source")
    python_exe = tmp_path / "gtavi-python.exe"
    python_exe.write_text("fake interpreter", encoding="utf-8")
    captured = {}

    class Result:
        returncode = 0
        stdout = "job: /tmp/fake-job\n8 candidates -> /tmp/fake-job/candidates.md"
        stderr = ""

    calls = []
    def fake_run(command, cwd, **kwargs):
        calls.append(command)
        captured["command"] = command
        captured["cwd"] = cwd
        if "env" in kwargs:
            captured["env"] = kwargs["env"]
        return Result()

    monkeypatch.setattr(money_geta.subprocess, "run", fake_run)
    monkeypatch.setattr(money_geta.shutil, "which", lambda name: f"/usr/bin/{name}")
    args = Namespace(
        gtavi_dir=gtavi, gtavi_python=python_exe, source=source,
        jobs_root=tmp_path / "jobs", top=8, min_seconds=15, max_seconds=40,
    )
    assert money_geta.run_moments(args) == 0
    assert captured["cwd"] == gtavi
    assert len(calls) == 2
    assert calls[0][1:3] == ["-c", "import numpy, faster_whisper"]
    assert captured["env"]["CLIP_DESK_HOME"].startswith(str(tmp_path / "jobs"))
    assert str(source) in captured["command"]
    assert "--top" in captured["command"]



def test_render_blocks_mpt_automatic_cross_post(tmp_path, monkeypatch):
    import json
    from argparse import Namespace
    from scripts import money_geta

    mpt = tmp_path / "mpt"
    mpt.mkdir()
    (mpt / "cli.py").write_text("# fake CLI", encoding="utf-8")
    (mpt / "config.toml").write_text("upload_post_auto_upload = true\n", encoding="utf-8")
    python_exe = mpt / "python.exe"
    python_exe.write_text("fake interpreter", encoding="utf-8")
    campaign = tmp_path / "campaign.json"
    campaign.write_text(json.dumps({
        "campaign_name": "test", "platform": "YouTube Shorts",
        "permissions_confirmed": True, "credits_confirmed": True,
        "sources": ["https://example.test/source"], "required_disclosures": [],
    }), encoding="utf-8")
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"local media")

    def forbidden_run(*args, **kwargs):
        raise AssertionError("MPT must not be launched while auto-publishing is enabled")

    monkeypatch.setattr(money_geta.subprocess, "run", forbidden_run)
    args = Namespace(
        mpt_dir=mpt, mpt_python=python_exe, campaign=campaign, materials=[media],
        subject="GTA VI test", aspect="9:16", count=1, language="en-US", voice=None,
    )
    assert money_geta.run_mpt(args) == 2


def test_live_recording_requires_explicit_confirmation(tmp_path):
    from argparse import Namespace
    from scripts import money_geta

    gtavi = tmp_path / "gtavi"
    (gtavi / "scripts").mkdir(parents=True)
    (gtavi / "scripts" / "live.py").write_text("# fake live script", encoding="utf-8")
    args = Namespace(
        gtavi_dir=gtavi, confirm_recording=False, url="https://www.youtube.com/watch?v=test",
        minutes=60, before=15, after=20, window=10, ratio=3, min_msgs=8,
        lag=8, cooldown=45, gtavi_python=None, jobs_root=tmp_path / "jobs",
    )
    assert money_geta.run_live(args) == 2


def test_cut_video_rejects_unknown_candidate_before_running_upstream(tmp_path, monkeypatch):
    import json
    from argparse import Namespace
    from scripts import money_geta

    gtavi = tmp_path / "gtavi"
    (gtavi / "scripts").mkdir(parents=True)
    (gtavi / "scripts" / "cut.py").write_text("# fake cut script", encoding="utf-8")
    job = tmp_path / "job"
    job.mkdir()
    (job / "candidates.json").write_text(json.dumps({"candidates": [{"n": 1}]}), encoding="utf-8")
    (job / "transcript.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(money_geta.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    args = Namespace(
        gtavi_dir=gtavi, gtavi_python=None, job_dir=job, pick=99,
        layout="blur", captions="word", hook="",
    )
    assert money_geta.run_cut(args) == 2


def test_run_manifest_updates_and_status_lists_it(tmp_path, capsys):
    import json
    from scripts.money_geta import show_status, write_manifest

    session = tmp_path / "jobs" / "session-1"
    manifest = write_manifest(session, stage="analyzed", source_path="local.mp4")
    write_manifest(session, stage="clip_ready", clip_path="clip.mp4")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["stage"] == "clip_ready"
    assert data["source_path"] == "local.mp4"
    assert data["clip_path"] == "clip.mp4"
    assert show_status(tmp_path / "jobs", 10) == 0
    assert "clip_ready" in capsys.readouterr().out
