import json

from scripts.campaign_registry import create_campaign
from scripts.money_geta import main
from scripts.project_registry import create_project
from scripts.providers.openverse import _normalize, save_image_candidates


def _setup(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setenv("MONEY_GETA_PROJECTS_DIR", str(root))
    create_project("CLI media", "viral", root=root)
    create_campaign("cli-media", "Campaign", "Instagram Reels", root=root)
    item = {"title":"City","url":"https://cdn.example.org/img.jpg","foreign_landing_url":"https://example.org/source",
        "creator":"Creator","creator_url":"https://example.org/creator","license":"by","license_version":"4.0",
        "license_url":"https://creativecommons.org/licenses/by/4.0/","source":"Test","category":"photograph",
        "thumbnail":"https://cdn.example.org/thumb.jpg","width":640,"height":480,"attribution":"Photo by Creator"}
    candidate = _normalize("city", [item])[0]
    save_image_candidates("cli-media", "campaign", [candidate], root=root)
    return candidate


def test_media_review_cli_records_and_checks_approval(tmp_path, monkeypatch, capsys):
    candidate = _setup(tmp_path, monkeypatch)
    code = main(["media-review", "--project", "cli-media", "--campaign", "campaign",
        "--candidate-id", candidate.candidate_id, "--decision", "approved", "--reviewer", "Operator",
        "--rights-evidence", "Original source license page checked", "--license", "CC BY 4.0",
        "--source-reviewed", "--attribution", "Creator"])
    assert code == 0
    assert "operator attestation" in capsys.readouterr().out
    code = main(["media-check", "--project", "cli-media", "--campaign", "campaign",
        "--candidate-id", candidate.candidate_id])
    assert code == 0
    assert "MEDIA_RIGHTS_REVIEW: PASS" in capsys.readouterr().out
