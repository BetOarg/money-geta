from argparse import Namespace
import json

from scripts import money_geta


def test_process_source_downloads_and_analyzes_in_one_session(tmp_path, monkeypatch, capsys):
    gtavi = tmp_path / "gtavi"
    gtavi.mkdir()
    jobs = tmp_path / "jobs"
    source_file = tmp_path / "downloaded.mp4"
    source_file.write_bytes(b"video")
    captured = {}

    def fake_download(url, session, ffmpeg_location):
        captured["download_session"] = session
        return source_file

    def fake_analyze(args, session_dir=None):
        captured["analysis_source"] = args.source
        captured["analysis_session"] = session_dir
        money_geta.write_manifest(session_dir, stage="analyzed", candidate_count=3)
        return 0

    monkeypatch.setattr(money_geta, "download_source", fake_download)
    monkeypatch.setattr(money_geta, "run_moments", fake_analyze)
    args = Namespace(
        confirm_rights=True, gtavi_dir=gtavi, gtavi_python=None,
        url="https://example.test/watch?v=abc&token=secret",
        ffmpeg_location=None, jobs_root=jobs, top=8,
        min_seconds=15, max_seconds=40,
    )

    assert money_geta.run_process_source(args) == 0
    assert captured["download_session"] == captured["analysis_session"]
    assert captured["analysis_source"] == source_file
    manifest_path = captured["analysis_session"] / "money-geta.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["stage"] == "analyzed"
    assert manifest["source_host"] == "example.test"
    assert "secret" not in manifest_path.read_text(encoding="utf-8")
    assert "WORKFLOW_SESSION:" in capsys.readouterr().out


def test_process_source_requires_rights_confirmation(tmp_path, capsys):
    args = Namespace(confirm_rights=False, gtavi_dir=tmp_path)
    assert money_geta.run_process_source(args) == 2
    assert "confirm-rights" in capsys.readouterr().out
