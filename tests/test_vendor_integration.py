from pathlib import Path

from scripts import money_geta


def test_vendored_gtavi_snapshot_is_present_and_is_default():
    vendor = money_geta.default_gtavi_dir()
    assert vendor == money_geta.ROOT / "vendor/gtavi-claudecode"
    for relative in (
        "LICENSE",
        "requirements.txt",
        "scripts/common.py",
        "scripts/moments.py",
        "scripts/cut.py",
        "scripts/check.py",
        "skills/moment-finder/SKILL.md",
        "skills/campaign-finder/SKILL.md",
        "SOURCE_SNAPSHOT.md",
    ):
        assert (vendor / relative).is_file(), relative


def test_process_source_defaults_to_vendored_gtavi(monkeypatch):
    captured = {}

    def fake_process(args):
        captured["gtavi_dir"] = args.gtavi_dir
        return 0

    monkeypatch.setattr(money_geta, "run_process_source", fake_process)
    result = money_geta.main([
        "process-source",
        "--url", "https://example.test/video",
        "--confirm-rights",
    ])

    assert result == 0
    assert captured["gtavi_dir"] == money_geta.default_gtavi_dir()


def test_cut_video_requires_creator_credit():
    import pytest

    with pytest.raises(SystemExit):
        money_geta.main([
            "cut-video",
            "--job-dir", str(Path("jobs/test")),
            "--pick", "1",
        ])
