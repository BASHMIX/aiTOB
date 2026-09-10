"""Email adapter tests use in-process sinks and never contact a provider."""

from __future__ import annotations

import pytest

from backend.core import email_delivery


def test_email_status_is_safe_and_fail_closed_without_provider(monkeypatch: pytest.MonkeyPatch):
    for key in ("RESEND_API_KEY", "EMAIL_FROM", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    status = email_delivery.public_email_status()
    assert status == {
        "provider": "none",
        "configured": False,
        "from_configured": False,
        "reason": "email provider is not configured",
    }


@pytest.mark.asyncio
async def test_resend_delivery_uses_explicit_provider_without_logging_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-secret")
    monkeypatch.setenv("EMAIL_FROM", "FNC no-reply@FNC.bashtech.xyz")
    calls: list[dict] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, headers, json):
            calls.append({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(email_delivery.httpx, "AsyncClient", lambda **_: FakeClient())
    assert await email_delivery.send_email(
        recipient="owner@example.test", subject="Test", text="hello",
    ) is True
    assert calls[0]["url"] == "https://api.resend.com/emails"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-resend-secret"
    assert calls[0]["json"]["from"] == "FNC no-reply@FNC.bashtech.xyz"
    assert email_delivery.public_email_status()["configured"] is True


@pytest.mark.asyncio
async def test_smtp_delivery_is_explicit_and_does_not_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.test")
    sent: list[tuple] = []

    def fake_send(*args):
        sent.append(args)
        return True

    monkeypatch.setattr(email_delivery, "_send_smtp", fake_send)
    assert await email_delivery.send_email(
        recipient="owner@example.test", subject="Test", text="hello",
    ) is True
    assert sent and sent[0][0] == "owner@example.test"
