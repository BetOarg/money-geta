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
