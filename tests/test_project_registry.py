from pathlib import Path
import pytest
from scripts.project_registry import create_project, get_project, list_projects, safe_slug
from scripts.campaign_registry import create_campaign, get_campaign, list_campaigns
from scripts.campaign_check import validate_campaign

def test_create_and_list_projects_with_profile_binding(tmp_path: Path):
    path = create_project("Noticias de tecnología", "news", topic="IA", brief="Explicar avances", root=tmp_path)
    project = get_project("noticias-de-tecnologia", tmp_path)
    assert path.is_file() and project["profile_id"] == "news"
    assert project["profile_name"] == "Noticias" and project["status"] == "draft"
    assert [p["project_id"] for p in list_projects(tmp_path)] == ["noticias-de-tecnologia"]

def test_duplicate_project_does_not_overwrite_existing_manifest(tmp_path: Path):
    path = create_project("Gaming", "gaming", root=tmp_path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError): create_project("Gaming", "gaming", root=tmp_path)
    assert path.read_bytes() == before

def test_unknown_profile_fails_before_creating_project(tmp_path: Path):
    with pytest.raises(KeyError): create_project("Bad Project", "unknown", root=tmp_path)
    assert not (tmp_path / "bad-project").exists()

def test_slug_normalizes_unicode_and_rejects_empty():
    assert safe_slug("Educación y Tecnología") == "educacion-y-tecnologia"
    with pytest.raises(ValueError): safe_slug("!!!")

def test_campaign_is_created_in_draft_and_fails_publication_gate(tmp_path: Path):
    create_project("Gaming", "gaming", root=tmp_path)
    path = create_campaign("gaming", "Primer video", "YouTube Shorts", root=tmp_path)
    campaign = get_campaign("gaming", "primer-video", tmp_path)
    assert path.is_file() and campaign["profile_id"] == "gaming"
    assert campaign["distribution"] == {"mode": "draft_only", "human_approval_required": True}
    assert campaign["permissions_confirmed"] is False and campaign["credits_confirmed"] is False
    assert validate_campaign(campaign)
    assert [item["campaign_id"] for item in list_campaigns("gaming", tmp_path)] == ["primer-video"]

def test_duplicate_campaign_does_not_overwrite_existing_campaign(tmp_path: Path):
    create_project("Gaming", "gaming", root=tmp_path)
    path = create_campaign("gaming", "Launch", "X", root=tmp_path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError): create_campaign("gaming", "Launch", "X", root=tmp_path)
    assert path.read_bytes() == before

def test_campaign_requires_existing_project(tmp_path: Path):
    with pytest.raises(ValueError, match="Cannot read project manifest"):
        create_campaign("missing", "Launch", "X", root=tmp_path)

def test_malformed_project_json_is_rejected(tmp_path: Path):
    folder = tmp_path / "bad"; folder.mkdir()
    (folder / "project.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="project manifest"): get_project("bad", tmp_path)

def test_projects_and_campaigns_cli(tmp_path: Path, monkeypatch, capsys):
    from scripts.money_geta import main
    monkeypatch.setenv("MONEY_GETA_PROJECTS_DIR", str(tmp_path))
    assert main(["projects", "create", "--name", "Educación", "--profile", "education"]) == 0
    assert "STATUS: draft" in capsys.readouterr().out
    assert main(["campaigns", "create", "--project", "educacion", "--name", "Lección 1", "--platform", "YouTube"]) == 0
    assert "permissions, credits and sources remain unconfirmed" in capsys.readouterr().out
    assert main(["projects", "list"]) == 0
    assert "educacion | Educación | education | draft" in capsys.readouterr().out
    assert main(["campaigns", "list", "--project", "educacion"]) == 0
    assert "leccion-1 | Lección 1 | YouTube | draft" in capsys.readouterr().out

def test_campaign_update_records_rights_and_explicit_attestations(tmp_path: Path):
    from scripts.campaign_registry import update_campaign
    from scripts.campaign_check import validate_campaign
    create_project("News", "news", root=tmp_path)
    create_campaign("news", "Launch", "X", root=tmp_path)
    update_campaign("news", "launch",
        sources=["https://example.test/article"],
        rights_evidence=["Publisher permission email stored locally"],
        disclosures=["AI-generated narration"],
        credits=["Source: Example Publisher"],
        confirm_permissions=True, confirm_credits=True, root=tmp_path)
    campaign = get_campaign("news", "launch", tmp_path)
    assert campaign["permissions_confirmed"] is True
    assert campaign["credits_confirmed"] is True
    assert campaign["rights_ledger"][0]["status"] == "operator_attested"
    assert validate_campaign(campaign) == []


def test_campaign_update_rejects_unpaired_rights_evidence(tmp_path: Path):
    from scripts.campaign_registry import update_campaign
    create_project("News", "news", root=tmp_path)
    create_campaign("news", "Launch", "X", root=tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        update_campaign("news", "launch", sources=["source"], rights_evidence=[], root=tmp_path)


def test_campaign_update_cannot_confirm_permissions_without_evidence(tmp_path: Path):
    from scripts.campaign_registry import update_campaign
    create_project("News", "news", root=tmp_path)
    create_campaign("news", "Launch", "X", root=tmp_path)
    with pytest.raises(ValueError, match="every source"):
        update_campaign("news", "launch", confirm_permissions=True, root=tmp_path)


def test_campaign_update_requires_explicit_no_credits_or_credit_record(tmp_path: Path):
    from scripts.campaign_registry import update_campaign
    create_project("News", "news", root=tmp_path)
    create_campaign("news", "Launch", "X", root=tmp_path)
    with pytest.raises(ValueError, match="no-credits-required"):
        update_campaign("news", "launch", confirm_credits=True, root=tmp_path)

def test_campaign_gate_rejects_missing_or_mismatched_rights_records(tmp_path: Path):
    from scripts.campaign_registry import update_campaign
    create_project("News", "news", root=tmp_path)
    create_campaign("news", "Launch", "X", root=tmp_path)
    update_campaign("news", "launch", sources=["source-a"], rights_evidence=["permission-ref"],
                    confirm_permissions=True, confirm_credits=True, no_credits_required=True, root=tmp_path)
    campaign = get_campaign("news", "launch", tmp_path)
    campaign["rights_ledger"][0]["source"] = "different-source"
    assert any("matching source" in issue for issue in validate_campaign(campaign))


def test_campaign_update_cli_records_attestations(tmp_path: Path, monkeypatch, capsys):
    from scripts.money_geta import main
    monkeypatch.setenv("MONEY_GETA_PROJECTS_DIR", str(tmp_path))
    assert main(["projects", "create", "--name", "Noticias", "--profile", "news"]) == 0
    capsys.readouterr()
    assert main(["campaigns", "create", "--project", "noticias", "--name", "Lanzamiento", "--platform", "X"]) == 0
    capsys.readouterr()
    assert main(["campaigns", "update", "--project", "noticias", "lanzamiento",
        "--source", "https://example.test/story", "--rights-evidence", "Permiso archivado",
        "--confirm-permissions", "--confirm-credits", "--no-credits-required"]) == 0
    assert "not legal clearance" in capsys.readouterr().out
    campaign = get_campaign("noticias", "lanzamiento", tmp_path)
    assert validate_campaign(campaign) == []
