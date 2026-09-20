"""Short-lived keyed-hash Start.gg bio verification challenges."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta


def issue_challenge(*, secret: bytes, ttl_seconds: int = 300, max_attempts: int = 5) -> dict[str, object]:
    code = secrets.token_urlsafe(8).upper()
    digest = hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()
    return {"code": code, "code_hash": digest, "expires_at": (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat(), "max_attempts": max_attempts, "attempt_count": 0}


def verify_challenge(*, secret: bytes, code: str, code_hash: str, expires_at: str, attempt_count: int, max_attempts: int = 5) -> tuple[bool, str]:
    if int(attempt_count) >= int(max_attempts):
        return False, "attempt_limit"
    try:
        if datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")) <= datetime.now(UTC):
            return False, "expired"
    except ValueError:
        return False, "expired"
    expected = hmac.new(secret, str(code).strip().encode(), hashlib.sha256).hexdigest()
    return (hmac.compare_digest(expected, str(code_hash)), "ok" if hmac.compare_digest(expected, str(code_hash)) else "mismatch")


__all__ = ["issue_challenge", "verify_challenge"]
