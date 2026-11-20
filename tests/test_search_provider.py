import json
from urllib.request import Request

import pytest

from scripts.providers.search import (
    SearchConfig,
    SearchConfigurationError,
    SearchRequestError,
    search_web,
)


def test_search_disabled_by_default():
    config = SearchConfig.from_env({
        "MONEY_GETA_SEARCH_PROVIDER": "brave",
        "MONEY_GETA_SEARCH_API_KEY": "test-key",
    })
    assert config.allow_requests is False
    with pytest.raises(SearchConfigurationError, match="requests are disabled"):
        search_web("AI video tools", config=config)


def test_requires_supported_provider_and_key():
    with pytest.raises(SearchConfigurationError, match="brave or tavily"):
        search_web("query", config=SearchConfig(provider="google", api_key="x"))
    with pytest.raises(SearchConfigurationError, match="API_KEY"):
        search_web("query", config=SearchConfig(provider="brave"))


def test_validates_limits_and_query():
    config = SearchConfig("brave", "key", True, max_results=21)
    with pytest.raises(SearchConfigurationError, match="max results"):
        search_web("query", config=config)
    config = SearchConfig("brave", "key", True)
    with pytest.raises(SearchConfigurationError, match="query"):
        search_web("  ", config=config)


def test_brave_normalizes_source_and_provenance(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return json.dumps({"web": {"results": [
                {"title": "Official source", "url": "https://example.org/page",
                 "description": "Evidence snippet", "page_age": "2 days ago"},
                {"title": "Bad URL", "url": "javascript:alert(1)"},
                {"title": "", "url": "https://example.org/empty"},
            ]}}).encode()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("scripts.providers.search.urlopen", fake_urlopen)
    config = SearchConfig("brave", "secret-key", True, country="AR", language="es")
    results = search_web("consulta de prueba", config=config)
    assert len(results) == 1
    item = results[0]
    assert item.provider == "brave"
    assert item.title == "Official source"
    assert item.snippet == "Evidence snippet"
    assert item.published_at == "2 days ago"
    assert item.retrieved_at
    assert len(item.evidence_id) == 64
    assert captured["request"].get_header("X-subscription-token") == "secret-key"
    assert "country=AR" in captured["request"].full_url
    assert captured["timeout"] == 30


def test_tavily_request_and_response(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return json.dumps({"results": [
                {"title": "Tavily source", "url": "https://example.net/story",
                 "content": "Source extract", "score": 0.91,
                 "published_date": "2026-11-19"}
            ]}).encode()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        body = json.loads(request.data.decode())
        captured["body"] = body
        return FakeResponse()

    monkeypatch.setattr("scripts.providers.search.urlopen", fake_urlopen)
    config = SearchConfig("tavily", "secret-tavily", True)
    results = search_web("latest video workflow", config=config)
    request = captured["request"]
    assert request.full_url == "https://api.tavily.com/search"
    assert request.get_header("Authorization") == "Bearer secret-tavily"
    assert captured["body"]["include_answer"] is False
    assert results[0].provider_score == 0.91
    assert results[0].published_at == "2026-11-19"


def test_provider_errors_never_echo_secret(monkeypatch):
    def fail(*_, **__):
        raise OSError("secret-key")
    monkeypatch.setattr("scripts.providers.search.urlopen", fail)
    config = SearchConfig("brave", "secret-key", True)
    with pytest.raises(SearchRequestError) as error:
        search_web("query", config=config)
    assert "secret-key" not in str(error.value)


def test_normalized_source_rejects_embedded_credentials(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return json.dumps({"web": {"results": [
                {"title": "Credential URL", "url": "https://user:pass@example.org"}
            ]}}).encode()
    monkeypatch.setattr("scripts.providers.search.urlopen", lambda *_, **__: FakeResponse())
    results = search_web("query", config=SearchConfig("brave", "key", True))
    assert results == []
