from pathlib import Path

from scripts.money_geta import PATCHES, verify_patches


def test_patch_manifest_is_complete():
    assert set(PATCHES) == {"live.py", "secrets_map.py"}
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
    (mpt / "config.toml").write_text("# local-only test config", encoding="utf-8")
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
        stdout = "--video-subject --video-source --video-materials --video-aspect --video-count --stop-at"
        stderr = ""

    calls = []
    def fake_run(command, cwd, check, **kwargs):
        calls.append(command)
        captured["command"] = command
        captured["cwd"] = cwd
        return Result()

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

    def fake_run(command, cwd, env, capture_output, text, check):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        return Result()

    monkeypatch.setattr(money_geta.subprocess, "run", fake_run)
    monkeypatch.setattr(money_geta.shutil, "which", lambda name: f"/usr/bin/{name}")
    args = Namespace(
        gtavi_dir=gtavi, gtavi_python=python_exe, source=source,
        jobs_root=tmp_path / "jobs", top=8, min_seconds=15, max_seconds=40,
    )
    assert money_geta.run_moments(args) == 0
    assert captured["cwd"] == gtavi
    assert captured["env"]["CLIP_DESK_HOME"].startswith(str(tmp_path / "jobs"))
    assert str(source) in captured["command"]
    assert "--top" in captured["command"]
