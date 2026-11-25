import hashlib
import json
import pytest

from scripts.session_audit import audit_sessions


def _manifest(root, name, stage, **extra):
    folder = root / name
    folder.mkdir(parents=True)
    payload = {"stage": stage, "job_id": name, "updated_at": "2026-01-01T00:00:00Z", **extra}
    (folder / "money-geta.json").write_text(json.dumps(payload), encoding="utf-8")
    return folder / "money-geta.json"


def test_audit_classifies_incomplete_active_failed_and_review_sessions(tmp_path):
    _manifest(tmp_path, "active", "rendering")
    _manifest(tmp_path, "new", "created")
    _manifest(tmp_path, "failed", "render_failed")
    _manifest(tmp_path, "review", "rendered_pending_human_review")
    _manifest(tmp_path, "done", "recorded")
    result = audit_sessions(tmp_path)
    by_id = {row["job_id"]: row["status"] for row in result["sessions"]}
    assert by_id == {
        "active": "interrupted_or_active",
        "new": "interrupted_or_active",
        "failed": "failed",
        "review": "human_review_pending",
        "done": "completed_stage",
    }
    assert "Read-only" in result["note"]


def test_audit_reports_malformed_manifest_as_blocked(tmp_path):
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "money-geta.json").write_text("{invalid", encoding="utf-8")
    report = audit_sessions(tmp_path)
    assert report["sessions"][0]["status"] == "blocked"


def test_audit_rejects_symlink_jobs_root(tmp_path):
    actual = tmp_path / "real"
    actual.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(actual, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable on this platform: {exc}")
    with pytest.raises(ValueError, match="symlink"):
        audit_sessions(alias)


def test_audit_limit_caps_number_of_manifests(tmp_path):
    for n in range(4):
        _manifest(tmp_path, f"job-{n}", "created")
    report = audit_sessions(tmp_path, limit=2)
    assert report["count"] == 2


def test_sessions_audit_cli_prints_json_and_exit_status(tmp_path, monkeypatch, capsys):
    _manifest(tmp_path, "incomplete", "created")
    monkeypatch.setenv("MONEY_GETA_JOBS_DIR", str(tmp_path))
    from scripts.money_geta import main
    assert main(["sessions", "audit", "--jobs-root", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert '"status": "interrupted_or_active"' in captured.out
    assert "Read-only audit" in captured.out


@pytest.mark.parametrize("schema_version", [2, 0, "1", True])
def test_audit_blocks_unsupported_session_schema(tmp_path, schema_version):
    folder = tmp_path / "future"
    folder.mkdir()
    (folder / "money-geta.json").write_text(
        json.dumps({"schema_version": schema_version, "stage": "created"}),
        encoding="utf-8",
    )
    result = audit_sessions(tmp_path)
    assert result["sessions"][0]["status"] == "blocked"
    assert "schema_version" in result["sessions"][0]["reason"]


def test_audit_accepts_legacy_manifest_without_schema_version(tmp_path):
    folder = tmp_path / "legacy"
    folder.mkdir()
    (folder / "money-geta.json").write_text(
        json.dumps({"stage": "recorded"}),
        encoding="utf-8",
    )
    result = audit_sessions(tmp_path)
    assert result["sessions"][0]["status"] == "completed_stage"


@pytest.mark.parametrize("limit", [0, -1, 501, True])
def test_audit_rejects_invalid_limit(tmp_path, limit):
    with pytest.raises(ValueError, match="between 1 and 500"):
        audit_sessions(tmp_path, limit=limit)


def test_audit_blocks_invalid_stage_type(tmp_path):
    folder = tmp_path / "invalid-stage"
    folder.mkdir()
    (folder / "money-geta.json").write_text(
        json.dumps({"schema_version": 1, "stage": ["rendering"]}),
        encoding="utf-8",
    )
    result = audit_sessions(tmp_path)
    assert result["sessions"][0]["status"] == "blocked"


def _resumable_source_session(root):
    from scripts.money_geta import write_manifest
    session = root / "project" / "live" / "session-test"
    session.mkdir(parents=True)
    source = session / "source.mp4"
    source.write_bytes(b"authorized local media")
    write_manifest(
        session,
        stage="source_ready",
        workflow="download-and-analyze",
        rights_confirmed=True,
        source_path=str(source),
        file_size=source.stat().st_size,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        top=8,
        min_seconds=15,
        max_seconds=40,
    )
    return session, source


def test_resume_source_requires_explicit_confirmation(tmp_path, capsys):
    from argparse import Namespace
    from scripts.money_geta import resume_source_session
    session, _ = _resumable_source_session(tmp_path)
    args = Namespace(
        confirm_resume=False, jobs_root=tmp_path, session_dir=session,
        gtavi_dir=tmp_path, gtavi_python=None,
    )
    assert resume_source_session(args) == 2
    assert "explicit --confirm-resume" in capsys.readouterr().out


def test_resume_source_runs_only_verified_pristine_checkpoint(tmp_path, monkeypatch):
    from argparse import Namespace
    import scripts.money_geta as cli
    session, source = _resumable_source_session(tmp_path)
    called = {}
    def fake_run_moments(args, session_dir=None):
        called["source"] = args.source
        called["session"] = session_dir
        called["top"] = args.top
        return 0
    monkeypatch.setattr(cli, "run_moments", fake_run_moments)
    args = Namespace(
        confirm_resume=True, jobs_root=tmp_path, session_dir=session,
        gtavi_dir=tmp_path, gtavi_python=None,
    )
    assert cli.resume_source_session(args) == 0
    assert called == {"source": source.resolve(), "session": session.resolve(), "top": 8}
    manifest = json.loads((session / "money-geta.json").read_text())
    assert manifest["stage"] == "analyzing"
    assert manifest["resume_count"] == 1
    assert manifest["source_sha256"]


def test_resume_source_blocks_existing_partial_analysis_outputs(tmp_path, capsys):
    from argparse import Namespace
    from scripts.money_geta import resume_source_session
    session, _ = _resumable_source_session(tmp_path)
    (session / "jobs").mkdir()
    args = Namespace(
        confirm_resume=True, jobs_root=tmp_path, session_dir=session,
        gtavi_dir=tmp_path, gtavi_python=None,
    )
    assert resume_source_session(args) == 2
    assert "possible partial outputs" in capsys.readouterr().out


def test_resume_source_blocks_changed_source_size(tmp_path, capsys):
    from argparse import Namespace
    from scripts.money_geta import resume_source_session
    session, source = _resumable_source_session(tmp_path)
    source.write_bytes(b"AuthoriZed local media")
    args = Namespace(
        confirm_resume=True, jobs_root=tmp_path, session_dir=session,
        gtavi_dir=tmp_path, gtavi_python=None,
    )
    assert resume_source_session(args) == 2
    assert "SHA-256 differs" in capsys.readouterr().out


def test_resume_source_blocks_checkpoint_without_original_hash(tmp_path, capsys):
    from argparse import Namespace
    from scripts.money_geta import resume_source_session
    session, _ = _resumable_source_session(tmp_path)
    manifest_path = session / "money-geta.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("source_sha256")
    manifest_path.write_text(json.dumps(manifest))
    args = Namespace(
        confirm_resume=True, jobs_root=tmp_path, session_dir=session,
        gtavi_dir=tmp_path, gtavi_python=None,
    )
    assert resume_source_session(args) == 2
    assert "original source SHA-256 is missing" in capsys.readouterr().out
