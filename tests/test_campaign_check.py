import json
from pathlib import Path

from scripts.campaign_check import check_file, validate_campaign


VALID = {
    "campaign_name": "GTA VI launch explainers",
    "platform": "YouTube",
    "permissions_confirmed": True,
    "credits_confirmed": True,
    "sources": ["https://example.invalid/source"],
    "required_disclosures": [],
}


def test_missing_campaign_fails_closed() -> None:
    passed, problems = check_file(None)
    assert not passed
    assert "campaign file not supplied" in problems


def test_incomplete_campaign_fails() -> None:
    data = dict(VALID, permissions_confirmed=False, sources=[])
    assert validate_campaign(data)


def test_valid_campaign_fields_pass(tmp_path: Path) -> None:
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(VALID), encoding="utf-8")
    passed, problems = check_file(path)
    assert passed
    assert problems == []


def test_malformed_json_fails(tmp_path: Path) -> None:
    path = tmp_path / "campaign.json"
    path.write_text("{broken", encoding="utf-8")
    passed, problems = check_file(path)
    assert not passed
    assert problems
