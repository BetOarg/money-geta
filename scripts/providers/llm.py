"""OpenAI-compatible LLM adapter with explicit request opt-in.

No network request is made unless MONEY_GETA_LLM_ALLOW_REQUESTS=true.
Credentials are read only from the process environment and are never persisted.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderConfigurationError(ValueError):
    """The provider is not configured safely."""


class ProviderRequestError(RuntimeError):
    """A provider request failed; messages never include credentials."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 45.0
    allow_requests: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "LLMConfig":
        env = os.environ if environ is None else environ
        return cls(
            base_url=env.get("MONEY_GETA_LLM_BASE_URL", "").strip(),
            model=env.get("MONEY_GETA_LLM_MODEL", "").strip(),
            api_key=env.get("MONEY_GETA_LLM_API_KEY") or None,
            timeout_seconds=float(env.get("MONEY_GETA_LLM_TIMEOUT", "45")),
            allow_requests=env.get("MONEY_GETA_LLM_ALLOW_REQUESTS", "").lower() == "true",
        )

    def validate(self) -> None:
        if not self.base_url or not self.model:
            raise ProviderConfigurationError(
                "Set MONEY_GETA_LLM_BASE_URL and MONEY_GETA_LLM_MODEL."
            )
        if not self.base_url.startswith(("https://", "http://")):
            raise ProviderConfigurationError("LLM base URL must use HTTP or HTTPS.")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 300:
            raise ProviderConfigurationError("LLM timeout must be between 0 and 300 seconds.")
        if self.base_url.startswith("https://") is False and not (
            self.base_url.startswith("http://localhost")
            or self.base_url.startswith("http://127.0.0.1")
        ):
            raise ProviderConfigurationError("Non-local LLM endpoints must use HTTPS.")


def _completion_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def chat_completion(
    messages: Sequence[Mapping[str, str]],
    *,
    config: LLMConfig | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Call an OpenAI-compatible Chat Completions endpoint after explicit opt-in."""
    cfg = config or LLMConfig.from_env()
    cfg.validate()
    if not cfg.allow_requests:
        raise ProviderConfigurationError(
            "LLM requests are disabled. Set MONEY_GETA_LLM_ALLOW_REQUESTS=true "
            "only after reviewing provider, model, quota and possible charges."
        )
    if not messages:
        raise ProviderConfigurationError("At least one message is required.")
    payload: dict[str, Any] = {"model": cfg.model, "messages": list(messages)}
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        if max_tokens < 1:
            raise ProviderConfigurationError("max_tokens must be positive.")
        payload["max_tokens"] = max_tokens
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = "Bearer " + cfg.api_key
    request = Request(
        _completion_url(cfg.base_url),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=cfg.timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ProviderRequestError(f"LLM provider returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError, OSError):
        raise ProviderRequestError("LLM provider request failed or timed out.") from None
    except (UnicodeError, json.JSONDecodeError):
        raise ProviderRequestError("LLM provider returned an invalid JSON response.") from None
    if not isinstance(result, dict):
        raise ProviderRequestError("LLM provider response must be a JSON object.")
    return result


def extract_text(response: Mapping[str, Any]) -> str:
    """Extract assistant text without assuming optional response metadata."""
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ProviderRequestError("LLM response is missing choices[0].message.content.") from None
    if not isinstance(content, str):
        raise ProviderRequestError("LLM response content is not plain text.")
    return content
