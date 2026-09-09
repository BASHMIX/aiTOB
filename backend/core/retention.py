"""Bounded retention housekeeping for authentication artifacts.

This module deliberately does not delete tournament, match, asset, provider,
or workspace records.  It only removes short-lived authentication material
after its expiry/consumption retention window.  The caller (a future
maintenance worker) supplies the clock so the policy is deterministic in
tests and can be audited in operations.
"""

from __future__ import annotations

import datetime as dt
import os

from backend.core.storage import dbapi as aiosqlite, is_postgres
from backend.core import database


DEFAULT_AUTH_RETENTION_DAYS = 30
MIN_AUTH_RETENTION_DAYS = 1
MAX_AUTH_RETENTION_DAYS = 3650


def auth_retention_days() -> int:
    """Return the configured retention period or fail closed on bad config."""
    raw = os.getenv("AITOB_AUTH_ARTIFACT_RETENTION_DAYS", str(DEFAULT_AUTH_RETENTION_DAYS)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("AITOB_AUTH_ARTIFACT_RETENTION_DAYS must be an integer") from exc
    if not MIN_AUTH_RETENTION_DAYS <= value <= MAX_AUTH_RETENTION_DAYS:
        raise RuntimeError(
            f"AITOB_AUTH_ARTIFACT_RETENTION_DAYS must be between {MIN_AUTH_RETENTION_DAYS} and {MAX_AUTH_RETENTION_DAYS}"
        )
    return value


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def purge_expired_auth_artifacts(
    *, now: dt.datetime | None = None, retention_days: int | None = None,
) -> dict[str, int]:
    """Purge expired/consumed auth artifacts atomically.

    Expired invitations are removed only after their expiry plus the retention
    period, preserving a safe audit window.  Used reset/verification tokens,
    expired MFA setup challenges, revoked/expired sessions, and old limiter
    buckets follow the same policy.  No workspace-owned operational data is
    touched, and the returned counts are safe operational metadata.
    """
    observed = now or _utcnow()
    days = auth_retention_days() if retention_days is None else int(retention_days)
    if not MIN_AUTH_RETENTION_DAYS <= days <= MAX_AUTH_RETENTION_DAYS:
        raise ValueError("retention_days is outside the supported safety range")
    cutoff = (observed - dt.timedelta(days=days)).isoformat()
    expiry_cutoff = observed.isoformat()
    counts: dict[str, int] = {}

    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN" if is_postgres() else "BEGIN IMMEDIATE")
        try:
            statements = {
                "password_reset_tokens": (
                    "DELETE FROM password_reset_tokens WHERE "
                    "(used_at IS NOT NULL AND used_at <= ?) OR expires_at <= ?",
                    (cutoff, cutoff),
                ),
                "email_verification_tokens": (
                    "DELETE FROM email_verification_tokens WHERE "
                    "(used_at IS NOT NULL AND used_at <= ?) OR expires_at <= ?",
                    (cutoff, cutoff),
                ),
                "workspace_invitations": (
                    "DELETE FROM workspace_invitations WHERE "
                    "(accepted_at IS NOT NULL AND accepted_at <= ?) OR "
                    "(cancelled_at IS NOT NULL AND cancelled_at <= ?) OR expires_at <= ?",
                    (cutoff, cutoff, cutoff),
                ),
                "user_mfa_setup": (
                    "DELETE FROM user_mfa_setup WHERE expires_at <= ?",
                    (expiry_cutoff,),
                ),
                "user_sessions": (
                    "DELETE FROM user_sessions WHERE expires_at <= ? OR "
                    "(revoked_at IS NOT NULL AND revoked_at <= ?)",
                    (cutoff, cutoff),
                ),
                "auth_rate_limits": (
                    "DELETE FROM auth_rate_limits WHERE window_started_at <= ?",
                    (cutoff,),
                ),
            }
            for table, (statement, params) in statements.items():
                result = await db.execute(statement, params)
                counts[table] = max(0, int(result.rowcount))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return counts

