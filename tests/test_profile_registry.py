import json
from pathlib import Path
import pytest
from scripts.profile_registry import get_profile, list_profiles, load_profiles

def test_default_registry_has_four_distinct_profiles():
    profiles = list_profiles()
    assert {item["id"] for item in profiles} == {"gaming", "viral", "news", "education"}
    assert len(profiles) == 4

def test_gta_vi_is_a_gaming_subprofile_not_a_global_profile():
    gaming = get_profile("gaming")
    assert "gta-vi" in gaming["subprofiles"]
    assert gaming["specialized_modules"] == ["vendor/gtavi-claudecode"]

def test_unknown_profile_fails_closed():
    with pytest.raises(KeyError, match="Unknown profile"):
        get_profile("not-a-profile")

def test_duplicate_profile_ids_are_rejected(tmp_path: Path):
    data = {"schema_version": 1, "profiles": [
        {"id": "same", "name": "One", "status": "planned", "capabilities": [], "rules": []},
        {"id": "same", "name": "Two", "status": "planned", "capabilities": [], "rules": []}
    ]}
    registry = tmp_path / "manifest.json"
    registry.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate profile id"):
        load_profiles(registry)

def test_profiles_cli_lists_profiles(capsys):
    from scripts.money_geta import main
    assert main(["profiles", "list"]) == 0
    output = capsys.readouterr().out
    assert "gaming | Gaming | partial" in output
    assert "viral | Viral | planned" in output


def test_profiles_cli_shows_one_profile(capsys):
    from scripts.money_geta import main
    assert main(["profiles", "show", "news"]) == 0
    output = capsys.readouterr().out
    assert '"id": "news"' in output


def test_system_example_defaults_to_draft_and_disables_paid_x():
    import json
    from pathlib import Path
    config = json.loads((Path(__file__).resolve().parents[1] / "config/system.example.json").read_text(encoding="utf-8"))
    assert config["distribution"]["draft_only"] is True
    assert config["distribution"]["human_approval_required"] is True
    assert config["x_research"]["enabled"] is False
    assert config["x_research"]["campaign_budget_usd"] == 0
