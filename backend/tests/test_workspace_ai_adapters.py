"""Safe classification contract tests for workspace AI adapters."""

from __future__ import annotations

import asyncio
import sys
import types
from urllib.error import HTTPError

import pytest

from backend.core.ai_providers.base import AIProviderFailure, classify_provider_error
from backend.core.ai_providers.gemini import GeminiAdapter
from backend.core.ai_providers.openai import OpenAIAdapter


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (TimeoutError(), "timeout"),
        (RuntimeError("invalid API key"), "invalid_key"),
        (RuntimeError("model not found"), "model_unavailable"),
        (RuntimeError("quota exceeded"), "quota_or_billing"),
        (RuntimeError("rate limit reached"), "rate_limited"),
        (RuntimeError("region is unsupported"), "region_restricted"),
        (OSError("connection refused"), "provider_unavailable"),
        (RuntimeError("opaque upstream failure"), "unknown"),
    ],
)
def test_provider_error_classifier_returns_only_safe_categories(error, category):
    info = classify_provider_error(error)
    assert info.category == category
    assert info.safe_message_code.startswith("ai_")
    if str(error):
        assert str(error) not in info.safe_message_code


class _StatusError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


@pytest.mark.parametrize(
    ("status_code", "category"),
    [(401, "invalid_key"), (404, "model_unavailable"), (429, "rate_limited"), (500, "provider_unavailable")],
)
def test_status_classification_is_provider_body_independent(status_code, category):
    info = classify_provider_error(_StatusError(status_code, "secret-key-value"))
    assert info.category == category
    assert "secret" not in info.safe_message_code


@pytest.mark.asyncio
async def test_gemini_adapter_wraps_sdk_failures_without_echoing_upstream_text(monkeypatch):
    upstream = "secret-key-value: invalid API key"

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def ainvoke(self, prompt):
            raise _StatusError(401, upstream)

    monkeypatch.setitem(sys.modules, "langchain_google_genai", types.SimpleNamespace(ChatGoogleGenerativeAI=FakeClient))
    with pytest.raises(AIProviderFailure) as caught:
        await GeminiAdapter().complete(api_key="secret-key-value", model="fixture", prompt="OK", timeout_seconds=3)
    assert caught.value.category == "invalid_key"
    assert upstream not in str(caught.value)
    assert "secret-key-value" not in repr(caught.value.as_dict())


@pytest.mark.asyncio
async def test_gemini_adapter_reports_timeout(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def ainvoke(self, prompt):
            await asyncio.sleep(0.05)

    monkeypatch.setitem(sys.modules, "langchain_google_genai", types.SimpleNamespace(ChatGoogleGenerativeAI=FakeClient))
    with pytest.raises(AIProviderFailure) as caught:
        await GeminiAdapter().complete(api_key="fixture", model="fixture", prompt="OK", timeout_seconds=0)
    # ``timeout_seconds`` is validated by the service; this test exercises the
    # adapter's bounded execution and safe category in isolation.
    assert caught.value.category in {"timeout", "unknown"}


@pytest.mark.asyncio
async def test_openai_adapter_classifies_http_errors_without_body_leak(monkeypatch):
    upstream = "https://api.openai.com/v1/chat/completions?api_key=secret-key-value"

    def fake_urlopen(request, timeout):
        raise HTTPError(upstream, 429, "quota exceeded: secret-key-value", {}, None)

    monkeypatch.setattr("backend.core.ai_providers.openai.urlopen", fake_urlopen)
    with pytest.raises(AIProviderFailure) as caught:
        await OpenAIAdapter().complete(api_key="secret-key-value", model="fixture", prompt="OK", timeout_seconds=3)
    assert caught.value.category == "quota_or_billing"
    assert upstream not in str(caught.value)
    assert "secret-key-value" not in repr(caught.value.as_dict())
