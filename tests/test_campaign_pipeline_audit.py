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

def test_claim_review_requires_latest_assessment_for_each_claim(tmp_path):
    folder = _campaign(tmp_path)
    (folder / "claim_ledger.jsonl").write_text(
        '{"schema_version":1,"event_type":"claim_created","claim_id":"a"}\n'
        '{"schema_version":1,"event_type":"claim_assessed","claim_id":"a","status":"supported"}\n'
        '{"schema_version":1,"event_type":"claim_created","claim_id":"b"}\n'
        '{"schema_version":1,"event_type":"claim_assessed","claim_id":"a","status":"unverified"}\n',
        encoding="utf-8",
    )
    report = audit_campaign("test-project", "test-campaign", root=tmp_path)
    stage = next(item for item in report["stages"] if item["stage"] == "claim_review")
    assert stage["status"] == "pending"
    assert stage["assessed"] == 1
    assert stage["latest_status_counts"] == {"unverified": 1}


def test_rejected_review_is_a_recorded_checkpoint_not_approval(tmp_path):
    folder = _campaign(tmp_path)
    (folder / "script_ledger.jsonl").write_text(
        '{"schema_version":1,"event_type":"script_registered","script_id":"s"}\n'
        '{"schema_version":1,"event_type":"script_decision","script_id":"s","decision":"rejected"}\n',
        encoding="utf-8",
    )
    (folder / "media_review_ledger.jsonl").write_text(
        '{"schema_version":1,"event_type":"media_review","candidate_id":"c","decision":"rejected"}\n',
        encoding="utf-8",
    )
    report = audit_campaign("test-project", "test-campaign", root=tmp_path)
    script_stage = next(item for item in report["stages"] if item["stage"] == "script_review")
    media_stage = next(item for item in report["stages"] if item["stage"] == "media_rights_review")
    assert script_stage["status"] == "complete"
    assert script_stage["approved_decisions"] == 0
    assert media_stage["status"] == "complete"
    assert media_stage["approved_decisions"] == 0
