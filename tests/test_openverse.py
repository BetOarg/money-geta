import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.campaign_registry import create_campaign
from scripts.project_registry import create_project
from scripts.money_geta import main
from scripts.providers.openverse import (
    ImageSearchConfig, ImageSearchConfigurationError, ImageSearchRequestError,
    _normalize, search_openverse, save_image_candidates,
)


def _response_item():
    return {
        "title": "Urban skyline",
        "url": "https://cdn.example.org/photo.jpg",
        "foreign_landing_url": "https://creativecommons.org/licenses/by/4.0/",
        "creator": "Photographer",
        "creator_url": "https://example.org/creator",
        "license": "by",
        "license_version": "4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source": "example",
        "category": "photograph",
        "thumbnail": "https://cdn.example.org/thumb.jpg",
        "width": 1920, "height": 1080,
        "attribution": "Photo by Photographer",
    }


def test_openverse_search_is_opt_in_and_commercial_filtered(monkeypatch):
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return json.dumps({"results": [_response_item()]}).encode()
    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return Response()
    monkeypatch.setattr("scripts.providers.openverse.urlopen", fake_urlopen)
    cfg = ImageSearchConfig(allow_requests=True, timeout_seconds=10, max_results=5)
    results = search_openverse("urban skyline", config=cfg, aspect_ratio="wide")
    params = parse_qs(urlsplit(captured["url"]).query)
    assert params["license_type"] == ["commercial"]
    assert params["aspect_ratio"] == ["wide"]
    assert params["page_size"] == ["5"]
    assert results[0].provider == "openverse"
    assert results[0].rights_status == "unverified"
    assert results[0].license == "by"


def test_image_search_requires_opt_in_and_valid_settings():
    with pytest.raises(ImageSearchConfigurationError, match="disabled"):
        search_openverse("city skyline", config=ImageSearchConfig())
    with pytest.raises(ImageSearchConfigurationError, match="official HTTPS"):
        ImageSearchConfig(endpoint="http://api.openverse.org/v1/images/").validate()
    with pytest.raises(ValueError):
        search_openverse("x" * 201, config=ImageSearchConfig(allow_requests=True))
    with pytest.raises(ValueError):
        search_openverse("city", config=ImageSearchConfig(allow_requests=True), aspect_ratio="panorama")


def test_normalization_rejects_bad_urls_and_incomplete_license_metadata():
    bad = _response_item()
    bad["url"] = "javascript:alert(1)"
    bad_items = [bad, {**_response_item(), "license": None}, "not a dict"]
    assert _normalize("query", bad_items) == []
    normalized = _normalize("query", [_response_item()])
    assert normalized[0].creator == "Photographer"
    assert normalized[0].attribution == "Photo by Photographer"


def test_save_image_candidates_deduplicates_and_keeps_rights_unverified(tmp_path):
    root = tmp_path / "projects"
    create_project("Openverse test", "viral", root=root)
    create_campaign("openverse-test", "Image campaign", "YouTube Shorts", root=root)
    candidate = _normalize("city", [_response_item()])[0]
    first = save_image_candidates("openverse-test", "image-campaign", [candidate, candidate], root=root)
    second = save_image_candidates("openverse-test", "image-campaign", [candidate], root=root)
    assert first["added"] == 1
    assert second["added"] == 0
    ledger = root / "openverse-test" / "campaigns" / "image-campaign" / "media_candidates.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["rights_status"] == "unverified"


def test_image_search_cli_is_opt_in(monkeypatch, capsys):
    monkeypatch.delenv("MONEY_GETA_IMAGE_SEARCH_ALLOW_REQUESTS", raising=False)
    code = main(["image-search", "--project", "test", "--campaign", "campaign", "--query", "city"])
    assert code == 2
    assert "disabled" in capsys.readouterr().out.lower()
