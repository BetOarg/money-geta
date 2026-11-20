import json
from urllib.request import Request

import pytest

from scripts.providers.llm import (
    LLMConfig,
    ProviderConfigurationError,
    ProviderRequestError,
    chat_completion,
    extract_text,
)


def test_env_config_defaults_to_no_network_requests():
    config = LLMConfig.from_env({
        "MONEY_GETA_LLM_BASE_URL": "https://api.example.test/v1",
        "MONEY_GETA_LLM_MODEL": "example-model",
    })
    assert config.allow_requests is False
    with pytest.raises(ProviderConfigurationError, match="requests are disabled"):
        chat_completion([{"role": "user", "content": "hello"}], config=config)


def test_requires_endpoint_and_model():
    with pytest.raises(ProviderConfigurationError, match="BASE_URL"):
        chat_completion([{"role": "user", "content": "hello"}], config=LLMConfig("", ""))


def test_rejects_insecure_remote_endpoint():
    config = LLMConfig("http://api.example.test/v1", "model", allow_requests=True)
    with pytest.raises(ProviderConfigurationError, match="HTTPS"):
        chat_completion([{"role": "user", "content": "hello"}], config=config)


def test_allows_local_http_gateway():
    LLMConfig("http://127.0.0.1:8080/v1", "local-model").validate()


def test_openai_compatible_request_and_response(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return json.dumps({
                "choices": [{"message": {"role": "assistant", "content": "Draft ready"}}]
            }).encode()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("scripts.providers.llm.urlopen", fake_urlopen)
    config = LLMConfig(
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "gemini-model", api_key="secret-test-key", timeout_seconds=20,
        allow_requests=True,
    )
    result = chat_completion(
        [{"role": "user", "content": "Write a neutral hook"}],
        config=config, max_tokens=120,
    )
    request = captured["request"]
    assert isinstance(request, Request)
    assert request.full_url.endswith("/chat/completions")
    assert request.get_header("Authorization") == "Bearer secret-test-key"
    body = json.loads(request.data.decode())
    assert body["model"] == "gemini-model"
    assert body["max_tokens"] == 120
    assert captured["timeout"] == 20
    assert extract_text(result) == "Draft ready"


def test_error_message_does_not_expose_api_key(monkeypatch):
    def fail(*_, **__):
        raise OSError("secret-test-key")
    monkeypatch.setattr("scripts.providers.llm.urlopen", fail)
    config = LLMConfig("https://api.example.test/v1", "model",
                       api_key="secret-test-key", allow_requests=True)
    with pytest.raises(ProviderRequestError) as error:
        chat_completion([{"role": "user", "content": "hello"}], config=config)
    assert "secret-test-key" not in str(error.value)


def test_rejects_malformed_provider_response():
    with pytest.raises(ProviderRequestError, match="missing choices"):
        extract_text({})
