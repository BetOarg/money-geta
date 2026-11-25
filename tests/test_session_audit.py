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
