from scripts.profile_audit import audit_profiles
from scripts.profile_registry import list_profiles


def test_audit_reports_every_default_profile_and_non_ready_status():
    report = audit_profiles(list_profiles())
    assert {item["profile"] for item in report} == {"gaming", "viral", "news", "education"}
    assert all(item["audit_status"] != "ready" for item in report)
    assert all(item["declared_status"] in {"partial", "planned"} for item in report)


def test_planned_capability_is_reported_as_gap():
    result = audit_profiles([{
        "id": "news", "status": "planned", "capabilities": ["translation"]
    }])[0]
    assert result["gaps"] == ["translation"]
    assert result["audit_status"] == "planned"


def test_unknown_capability_fails_readiness_and_is_explicit():
    result = audit_profiles([{
        "id": "custom", "status": "ready", "capabilities": ["not-implemented"]
    }])[0]
    assert result["unknown_capabilities"] == ["not-implemented"]
    assert result["gaps"] == ["not-implemented"]
    assert result["audit_status"] == "planned"


def test_gta_vi_specific_capabilities_are_marked_partial_for_gaming():
    result = audit_profiles([{
        "id": "gaming", "status": "partial",
        "capabilities": ["moment-detection", "clip-editing"]
    }])[0]
    assert all(item["status"] == "partial" for item in result["capabilities"])
    assert all("GTA VI" in item["note"] for item in result["capabilities"])


def test_profiles_audit_cli_is_read_only_and_reports_gaps(capsys):
    from scripts.money_geta import main
    assert main(["profiles", "audit"]) == 0
    output = capsys.readouterr().out
    assert '"profile": "gaming"' in output
    assert '"audit_status": "partial"' in output
    assert '"profile": "education"' in output
    assert '"gaps": [' in output


def test_moment_detection_is_not_claimed_for_non_gaming_profiles():
    result = audit_profiles([{
        "id": "viral", "status": "planned", "capabilities": ["moment-detection"]
    }])[0]
    assert result["capabilities"][0]["status"] == "planned"
    assert result["gaps"] == ["moment-detection"]
