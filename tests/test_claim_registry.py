import json
import pytest
from scripts import claim_registry as claims


def _campaign(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    folder = root / "p" / "campaigns" / "c"
    folder.mkdir(parents=True)
    (root / "p" / "project.json").write_text("{}", encoding="utf-8")
    (folder / "campaign.json").write_text("{}", encoding="utf-8")
    rows = [
        {"schema_version": 1, "evidence_id": "e1", "final_url": "https://news-one.example/story"},
        {"schema_version": 1, "evidence_id": "e2", "final_url": "https://news-two.example/story"},
    ]
    (folder / "source_ledger.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
    monkeypatch.setattr(claims, "get_project", lambda *a, **k: {})
    monkeypatch.setattr(claims, "get_campaign", lambda *a, **k: {})
    monkeypatch.setattr(claims, "safe_slug", lambda value: value)
    return root


def test_claim_starts_unverified_and_requires_known_evidence(tmp_path, monkeypatch):
    root = _campaign(tmp_path, monkeypatch)
    with pytest.raises(claims.ClaimRegistryError, match="Unknown evidence"):
        claims.create_claim("p", "c", "A factual statement", ["missing"], root=root)
    item = claims.create_claim("p", "c", "A factual statement", ["e1"], root=root)
    assert item["status"] == "unverified"
    assert claims.list_claims("p", "c", root=root)[0]["status"] == "unverified"


def test_supported_requires_two_hosts_and_human_independence_attestation(tmp_path, monkeypatch):
    root = _campaign(tmp_path, monkeypatch)
    item = claims.create_claim("p", "c", "A factual statement", ["e1"], root=root)
    with pytest.raises(claims.ClaimRegistryError, match="two distinct hostnames"):
        claims.assess_claim("p", "c", item["claim_id"], "supported", "Reviewed source material.", root=root)
    item = claims.create_claim("p", "c", "Another factual statement", ["e1", "e2"], root=root)
    with pytest.raises(claims.ClaimRegistryError, match="independence"):
        claims.assess_claim("p", "c", item["claim_id"], "supported", "Reviewed two sources carefully.", root=root)
    assessed = claims.assess_claim("p", "c", item["claim_id"], "supported",
                                   "Both sources independently confirm the same claim.",
                                   independence_attested=True, root=root)
    assert assessed["status"] == "supported"
    assert claims.list_claims("p", "c", root=root)[1]["status"] == "supported"


def test_contradicted_requires_conflict_summary(tmp_path, monkeypatch):
    root = _campaign(tmp_path, monkeypatch)
    item = claims.create_claim("p", "c", "A factual statement", ["e1", "e2"], root=root)
    with pytest.raises(claims.ClaimRegistryError, match="conflict summary"):
        claims.assess_claim("p", "c", item["claim_id"], "contradicted",
                            "Sources disagree with one another.", root=root)
    result = claims.assess_claim("p", "c", item["claim_id"], "contradicted",
                                 "Reviewed both source records and their dates.",
                                 contradiction_summary="One source says yes, the other says no.", root=root)
    assert result["status"] == "contradicted"


def test_claim_ledger_is_append_only_and_fails_closed_on_corruption(tmp_path, monkeypatch):
    root = _campaign(tmp_path, monkeypatch)
    item = claims.create_claim("p", "c", "A factual statement", ["e1"], root=root)
    claims.assess_claim("p", "c", item["claim_id"], "unsupported", "Evidence does not support this statement.", root=root)
    ledger = root / "p" / "campaigns" / "c" / "claim_ledger.jsonl"
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2
    ledger.write_text("{broken\n", encoding="utf-8")
    with pytest.raises(claims.ClaimRegistryError, match="malformed"):
        claims.list_claims("p", "c", root=root)
    with pytest.raises(claims.ClaimRegistryError, match="malformed"):
        claims.create_claim("p", "c", "Another statement", ["e1"], root=root)
