"""Explicit email delivery adapter for account verification and recovery.

Resend is preferred when ``RESEND_API_KEY`` and ``EMAIL_FROM`` are present.
SMTP remains supported for deployments that choose it instead.  The adapter
never returns or logs credentials and callers may keep account endpoints
enumeration-safe when delivery is unavailable.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.message import EmailMessage
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class EmailDeliveryConfig:
    provider: str
    configured: bool
    from_address: str | None
    reason: str


def get_email_delivery_config() -> EmailDeliveryConfig:
    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    from_address = os.getenv("EMAIL_FROM", "").strip() or os.getenv("SMTP_FROM", "").strip()
    if resend_key and from_address:
        return EmailDeliveryConfig("resend", True, from_address, "configured")
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    if smtp_host and from_address and smtp_user and smtp_password:
        return EmailDeliveryConfig("smtp", True, from_address, "configured")
    return EmailDeliveryConfig("none", False, None, "email provider is not configured")


async def send_email(*, recipient: str, subject: str, text: str) -> bool:
    """Send one plain-text message through the explicitly configured adapter.

    No automatic provider fallback is performed. Each configured provider is
    used directly, and an unavailable provider returns ``False``.
    """
    config = get_email_delivery_config()
    if not config.configured:
        return False
    if config.provider == "resend":
        api_key = os.getenv("RESEND_API_KEY", "").strip()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"from": config.from_address, "to": [recipient], "subject": subject, "text": text},
                )
                response.raise_for_status()
        except (httpx.HTTPError, ValueError):
            return False
        return True
    if config.provider == "smtp":
        try:
            port = int(os.getenv("SMTP_PORT", "587"))
            return await asyncio.to_thread(
                _send_smtp, recipient, subject, text, str(config.from_address),
                os.getenv("SMTP_HOST", "").strip(), port,
                os.getenv("SMTP_USERNAME", "").strip(), os.getenv("SMTP_PASSWORD", "").strip(),
            )
        except (OSError, ValueError):
            return False
    return False


def _send_smtp(recipient: str, subject: str, text: str, sender: str, host: str, port: int, username: str, password: str) -> bool:
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, recipient, subject
    message.set_content(text)
    with smtplib.SMTP(host, port, timeout=15) as client:
        client.starttls()
        client.login(username, password)
        client.send_message(message)
    return True


def public_email_status() -> dict[str, object]:
    """Return a safe status projection suitable for a platform-admin UI."""
    config = get_email_delivery_config()
    return {
        "provider": config.provider,
        "configured": config.configured,
        "from_configured": bool(config.from_address),
        "reason": config.reason,
    }
