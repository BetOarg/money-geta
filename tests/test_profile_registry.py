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
