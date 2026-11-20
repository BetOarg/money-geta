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


def _project_campaign(tmp_path: Path, factual_claims_required: bool = True) -> tuple[Path, Path]:
    projects = tmp_path / "projects"
    folder = projects / "p" / "campaigns" / "c"
    folder.mkdir(parents=True)
    (projects / "p" / "project.json").write_text("{}", encoding="utf-8")
    data = {
        "schema_version": 1, "project_id": "p", "campaign_id": "c",
        "campaign_name": "Factual campaign", "platform": "YouTube",
        "permissions_confirmed": True, "credits_confirmed": True,
        "sources": ["source-a", "source-b"],
        "source_evidence": [
            {"source": "source-a", "reference": "rights-a"},
            {"source": "source-b", "reference": "rights-b"},
        ],
        "rights_ledger": [
            {"source": "source-a", "evidence": "rights-a", "status": "operator_attested"},
            {"source": "source-b", "evidence": "rights-b", "status": "operator_attested"},
        ],
        "permission_attestation": {"confirmed": True, "confirmed_at": "2026-01-01T00:00:00Z"},
        "credit_attestation": {"confirmed": True, "confirmed_at": "2026-01-01T00:00:00Z", "no_credits_required": True},
        "credit_records": [], "required_disclosures": [],
        "factual_claims_required": factual_claims_required,
    }
    path = folder / "campaign.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    source_rows = [
        {"schema_version": 1, "evidence_id": "e1", "final_url": "https://source-one.example/a"},
        {"schema_version": 1, "evidence_id": "e2", "final_url": "https://source-two.example/b"},
    ]
    (folder / "source_ledger.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in source_rows), encoding="utf-8"
    )
    return projects, path


def test_factual_campaign_without_claim_ledger_is_blocked(tmp_path: Path) -> None:
    _, path = _project_campaign(tmp_path)
    passed, problems = check_file(path)
    assert not passed
    assert any("no claim_ledger.jsonl" in item for item in problems)


def test_factual_claim_must_be_assessed_supported_before_campaign_passes(tmp_path: Path, monkeypatch) -> None:
    from scripts import claim_registry
    projects, path = _project_campaign(tmp_path)
    monkeypatch.setattr(claim_registry, "get_project", lambda *args, **kwargs: {})
    monkeypatch.setattr(claim_registry, "get_campaign", lambda *args, **kwargs: {})
    monkeypatch.setattr(claim_registry, "safe_slug", lambda value: value)

    claim = claim_registry.create_claim("p", "c", "The stated fact is accurate.", ["e1", "e2"], root=projects)
    passed, problems = check_file(path)
    assert not passed
    assert any("is unverified" in item for item in problems)

    claim_registry.assess_claim(
        "p", "c", claim["claim_id"], "supported",
        "Both independent sources directly corroborate this statement.",
        independence_attested=True, root=projects,
    )
    passed, problems = check_file(path)
    assert passed
    assert problems == []


def test_non_factual_campaign_can_pass_without_claim_ledger(tmp_path: Path) -> None:
    _, path = _project_campaign(tmp_path, factual_claims_required=False)
    passed, problems = check_file(path)
    assert passed
    assert problems == []
