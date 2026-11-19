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

    mpt = tmp_path / "mpt"
    mpt.mkdir()
    (mpt / "cli.py").write_text("# fake CLI", encoding="utf-8")
    (mpt / "config.toml").write_text("upload_post_auto_upload = false\n", encoding="utf-8")
    python_exe = mpt / "python.exe"
    python_exe.write_text("fake interpreter", encoding="utf-8")
    campaign = tmp_path / "campaign.json"
    campaign.write_text(json.dumps({
        "campaign_name": "test",
        "platform": "YouTube Shorts",
        "permissions_confirmed": True,
        "credits_confirmed": True,
        "sources": ["https://example.test/source"],
        "required_disclosures": [],
    }), encoding="utf-8")
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not rendered; command is mocked")
    captured = {}

    class Result:
        returncode = 0
        stderr = ""

    video = mpt / "storage" / "tasks" / "test-task" / "final-1.mp4"
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
        language="en-US", voice=None,
    )
    assert money_geta.run_mpt(args) == 0
    assert captured["cwd"] == mpt
    assert len(calls) == 2
    assert calls[0][-1] == "--help"
    assert str(mpt / "cli.py") in captured["command"]
    assert "--video-source" in captured["command"]
    assert captured["command"][captured["command"].index("--video-source") + 1] == "local"
    assert "--video-materials" in captured["command"]


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
