from scripts.campaign_pipeline_audit import audit_campaign
from scripts.campaign_registry import create_campaign
from scripts.project_registry import create_project


def _campaign(tmp_path):
    create_project("Test Project", "news", root=tmp_path)
    create_campaign("test-project", "Test Campaign", "YouTube Shorts", root=tmp_path)
    return tmp_path / "test-project" / "campaigns" / "test-campaign"


def test_audit_reports_checkpoint_inventory_without_mutating_campaign(tmp_path):
    folder = _campaign(tmp_path)
    (folder / "research").mkdir()
    (folder / "research" / "sample.json").write_text("{}", encoding="utf-8")
    (folder / "source_ledger.jsonl").write_text(
        '{"schema_version":1,"evidence_id":"e1","final_url":"https://example.com"}\n', encoding="utf-8"
    )
    report = audit_campaign("test-project", "test-campaign", root=tmp_path)
    assert report["checkpoint_count"] == 14
    assert report["completed_checkpoints"] >= 2
    assert report["campaign_gate_passed"] is False
    assert next(item for item in report["stages"] if item["stage"] == "research_reports")["count"] == 1
    assert next(item for item in report["stages"] if item["stage"] == "captured_sources")["count"] == 1
    assert not (folder / "artifact_ledger.jsonl").exists()


def test_audit_is_safe_for_missing_optional_ledgers(tmp_path):
    _campaign(tmp_path)
    report = audit_campaign("test-project", "test-campaign", root=tmp_path)
    assert all(stage["status"] in {"pending", "blocked", "complete"} for stage in report["stages"])
    assert report["completed_checkpoints"] == 0


def test_audit_reports_malformed_ledger_as_blocked(tmp_path):
    folder = _campaign(tmp_path)
    (folder / "source_ledger.jsonl").write_text("{broken-json\n", encoding="utf-8")
    report = audit_campaign("test-project", "test-campaign", root=tmp_path)
    source_stage = next(item for item in report["stages"] if item["stage"] == "captured_sources")
    assert source_stage["status"] == "blocked"
    assert "malformed" in source_stage["error"]

def test_campaign_audit_cli_outputs_json(tmp_path, capsys, monkeypatch):
    folder = _campaign(tmp_path)
    monkeypatch.setenv("MONEY_GETA_PROJECTS_DIR", str(tmp_path))
    from scripts.money_geta import main
    assert main(["campaigns", "audit", "--project", "test-project", "test-campaign"]) == 0
    output = capsys.readouterr().out
    assert '"campaign_id": "test-campaign"' in output
    assert '"campaign_gate_passed": false' in output
    assert '"stage": "editable_timelines"' in output
