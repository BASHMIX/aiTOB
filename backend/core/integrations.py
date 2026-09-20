"""Account-scoped external integrations and encrypted credential storage.

No caller may fall back to a global provider secret.  A missing service master key
or malformed ciphertext is deliberately a hard configuration failure.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.core.storage import dbapi
from cryptography.fernet import Fernet, InvalidToken

from backend.core import database


def _database_target() -> str:
    """Resolve the configured PostgreSQL target at call time."""
    return database.DATABASE_DSN


class IntegrationError(RuntimeError):
    pass


class IntegrationSecretUnavailable(IntegrationError):
    pass


class IntegrationAccountInUse(IntegrationError):
    pass


# Provider identities are deliberately centralized here so account creation,
# API projections, and background workers cannot drift into accepting a global
# or unsupported integration type.  ``gemini`` and ``openai`` are customer-owned
# AI accounts; aiTOB never treats them as platform billing credentials.
SUPPORTED_PROVIDER_TYPES = frozenset({
    "startgg", "challonge", "discord", "gemini", "openai",
})
SUPPORTED_INTEGRATION_PROVIDERS = SUPPORTED_PROVIDER_TYPES

CONNECTION_STATES = frozenset({
    "missing", "configured_untested", "verified", "degraded", "disabled",
})
CONNECTION_FAILURE_CATEGORIES = frozenset({
    "invalid_key", "model_unavailable", "quota_or_billing", "rate_limited",
    "region_restricted", "timeout", "provider_unavailable",
    "missing_permission", "missing_credential", "unknown",
})

# Metadata is safe, non-secret account health/context only.  Unknown keys are
# ignored so an upstream response or credential-shaped field cannot accidentally
# become durable data or a browser projection.
SAFE_ACCOUNT_METADATA_KEYS = frozenset({
    "display_identity", "display_name", "granted_scopes", "scope_names",
    "token_expires_at", "expires_at", "guild_id", "guild_name", "guild_label",
    "capabilities", "capability_hints", "oauth_application_id",
})
SECRET_METADATA_PARTS = frozenset({
    "token", "secret", "password", "credential", "authorization", "cookie",
    "apikey", "accesskey", "privatekey", "ciphertext", "rawresponse",
    "responsebody", "headers", "requestbody",
})


def _normalized_key(value: object) -> str:
    return "".join(char for char in str(value).strip().lower() if char.isalnum())


def _is_secret_key(value: object) -> bool:
    normalized = _normalized_key(value)
    return (
        not normalized
        or normalized in SECRET_METADATA_PARTS
        or any(part in normalized for part in SECRET_METADATA_PARTS)
    )


def _safe_metadata(value: Any) -> dict[str, Any]:
    """Return an allow-listed metadata projection without credential-shaped data."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        # The explicit allow-list is the primary boundary.  In particular,
        # ``token_expires_at`` is safe metadata even though its name contains
        # the word ``token``.
        if key_text not in SAFE_ACCOUNT_METADATA_KEYS:
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            result[key_text] = item
        elif isinstance(item, (list, tuple, set)):
            safe_items = [entry for entry in item if isinstance(entry, (str, int, float, bool))]
            result[key_text] = safe_items[:64]
        elif isinstance(item, dict):
            # Capability/display maps are useful health metadata, but recurse
            # through the same secret key check and cap the result.
            nested = {
                str(nested_key): nested_value
                for nested_key, nested_value in item.items()
                if not _is_secret_key(nested_key)
                and isinstance(nested_value, (str, int, float, bool))
            }
            result[key_text] = dict(list(nested.items())[:64])
    return result


def _safe_json_metadata(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return _safe_metadata(raw)
    try:
        decoded = json.loads(str(raw or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return _safe_metadata(decoded)


def _safe_audit_detail(value: Any, *, depth: int = 0) -> Any:
    """Retain operational audit context while dropping secret-shaped values."""
    if depth > 3:
        return None
    if isinstance(value, dict):
        return {
            str(key): _safe_audit_detail(item, depth=depth + 1)
            for key, item in list(value.items())[:64]
            if not _is_secret_key(key)
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe_audit_detail(item, depth=depth + 1) for item in list(value)[:64]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        # Upstream messages are never audit detail; bound ordinary labels to
        # keep a provider response from becoming an unbounded log payload.
        return value[:240] if isinstance(value, str) else value
    return None


def _validate_provider_type(provider_type: str) -> str:
    normalized = str(provider_type or "").strip().lower()
    if normalized not in SUPPORTED_PROVIDER_TYPES:
        raise IntegrationError("Unsupported integration provider type.")
    return normalized


def _validate_health_value(value: str | None, allowed: frozenset[str], label: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized not in allowed:
        raise IntegrationError(f"Unsupported integration {label}.")
    return normalized


def _safe_message_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = str(value).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,119}", code):
        raise IntegrationError("Integration health message code is invalid.")
    return code


def _public_health(row: dict[str, Any], *, configured: bool | None = None, enabled: bool | None = None) -> dict[str, Any]:
    """Project only non-secret connection health fields."""
    raw_state = str(row.get("state") or "missing").strip().lower()
    state = raw_state if raw_state in CONNECTION_STATES else "degraded"
    raw_failure = row.get("failure_category")
    failure_category = (
        str(raw_failure).strip().lower()
        if raw_failure is not None
        and str(raw_failure).strip().lower() in CONNECTION_FAILURE_CATEGORIES
        else ("unknown" if raw_failure is not None else None)
    )
    raw_message = row.get("safe_message_code")
    message = str(raw_message).strip().lower() if raw_message is not None else None
    safe_message = message if message and re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,119}", message) else None
    raw_revision = row.get("credential_revision")
    try:
        revision = int(raw_revision) if raw_revision is not None and int(raw_revision) >= 1 else None
    except (TypeError, ValueError):
        revision = None
    value = {
        "account_id": row.get("account_id"),
        "workspace_id": row.get("workspace_id"),
        "state": state,
        "failure_category": failure_category,
        "safe_message_code": safe_message,
        "credential_revision": revision,
        "last_tested_at": row.get("last_tested_at"),
        "last_succeeded_at": row.get("last_succeeded_at"),
        "updated_at": row.get("updated_at"),
    }
    if configured is not None:
        value["configured"] = configured
    if enabled is not None:
        value["enabled"] = enabled
    return value


async def _credential_revision(
    db: dbapi.Connection,
    owner_id: str,
    secret_type: str | None = None,
    *,
    owner_kind: str = "account",
) -> int | None:
    if secret_type is None:
        row = await (await db.execute(
            "SELECT MAX(credential_revision) FROM integration_credentials WHERE owner_kind=? AND owner_id=?",
            (owner_kind, owner_id),
        )).fetchone()
    else:
        row = await (await db.execute(
            "SELECT credential_revision FROM integration_credentials WHERE owner_kind=? AND owner_id=? AND secret_type=?",
            (owner_kind, owner_id, secret_type),
        )).fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


async def _upsert_connection_health(
    db: dbapi.Connection,
    account_id: str,
    workspace_id: str,
    *,
    state: str,
    failure_category: str | None = None,
    safe_message_code: str | None = None,
    credential_revision: int | None = None,
    last_tested_at: str | None = None,
    last_succeeded_at: str | None = None,
) -> dict[str, Any]:
    """Write health state without accepting upstream text or secret material."""
    db.row_factory = dbapi.Row
    state = _validate_health_value(state, CONNECTION_STATES, "health state") or "missing"
    failure_category = _validate_health_value(
        failure_category, CONNECTION_FAILURE_CATEGORIES, "failure category"
    )
    safe_message_code = _safe_message_code(safe_message_code)
    if credential_revision is not None and int(credential_revision) < 1:
        raise IntegrationError("Credential revision must be positive.")
    current_revision = await _credential_revision(db, account_id)
    if credential_revision is not None:
        supplied_revision = int(credential_revision)
        # A delayed provider response must never overwrite health for a newer
        # key.  Removal is the one intentional exception: there is no current
        # credential revision after ciphertext is deleted, but retaining the
        # last revision on a ``missing`` health row is useful audit metadata.
        if current_revision != supplied_revision and not (
            state == "missing" and current_revision is None
        ):
            row = await (await db.execute(
                "SELECT * FROM integration_connection_health WHERE account_id=?",
                (account_id,),
            )).fetchone()
            if row:
                return _public_health(dict(row))
            return _public_health({
                "account_id": account_id,
                "workspace_id": workspace_id,
                "state": "missing",
                "failure_category": "missing_credential",
                "credential_revision": current_revision,
            })
        credential_revision = supplied_revision
    else:
        credential_revision = current_revision
    await db.execute(
        """
        INSERT INTO integration_connection_health
            (account_id, workspace_id, state, failure_category,
             safe_message_code, credential_revision, last_tested_at,
             last_succeeded_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(account_id) DO UPDATE SET
            workspace_id=excluded.workspace_id,
            state=excluded.state,
            failure_category=excluded.failure_category,
            safe_message_code=excluded.safe_message_code,
            credential_revision=excluded.credential_revision,
            last_tested_at=excluded.last_tested_at,
            last_succeeded_at=excluded.last_succeeded_at,
            updated_at=excluded.updated_at
        WHERE (
            excluded.credential_revision IS NULL
            AND integration_connection_health.credential_revision IS NULL
        ) OR (
            excluded.credential_revision IS NOT NULL
            AND (
                integration_connection_health.credential_revision IS NULL
                OR integration_connection_health.credential_revision <= excluded.credential_revision
            )
        )
        """,
        (
            account_id,
            workspace_id,
            state,
            failure_category,
            safe_message_code,
            credential_revision,
            last_tested_at,
            last_succeeded_at,
            _now(),
        ),
    )
    row = await (await db.execute(
        "SELECT * FROM integration_connection_health WHERE account_id=?",
        (account_id,),
    )).fetchone()
    return _public_health(dict(row))


async def get_integration_health(
    account_id: str,
    *,
    workspace_id: str | None = None,
) -> dict[str, Any] | None:
    """Return safe connection health metadata for one workspace account."""
    account = await get_integration_account(
        account_id, workspace_id=workspace_id, active_only=False
    )
    if not account:
        return None
    configured = bool(await configured_secret_types(account_id))
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        row = await (await db.execute(
            "SELECT * FROM integration_connection_health WHERE account_id=? AND workspace_id=?",
            (account_id, account.get("workspace_id") or workspace_id),
        )).fetchone()
    if not row:
        default_state = (
            "disabled"
            if account.get("status") != "active"
            else ("missing" if not configured else "configured_untested")
        )
        return _public_health(
            {
                "account_id": account_id,
                "workspace_id": account.get("workspace_id") or workspace_id,
                "state": default_state,
                "failure_category": (
                    "missing_credential"
                    if default_state == "missing"
                    else None
                ),
                "credential_revision": None,
            },
            configured=configured,
            enabled=account.get("status") == "active",
        )
    return _public_health(
        dict(row), configured=configured, enabled=account.get("status") == "active"
    )


async def update_integration_health(
    account_id: str,
    state: str,
    *,
    workspace_id: str | None = None,
    failure_category: str | None = None,
    safe_message_code: str | None = None,
    credential_revision: int | None = None,
    last_tested_at: str | None = None,
    last_succeeded_at: str | None = None,
) -> dict[str, Any]:
    """Record classified provider health and return its safe projection."""
    account = await get_integration_account(
        account_id, workspace_id=workspace_id, active_only=False
    )
    if not account:
        raise IntegrationError("Integration account is unavailable in this workspace.")
    effective_workspace = account.get("workspace_id") or workspace_id
    if not effective_workspace:
        raise IntegrationError("Integration account has no workspace owner.")
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        value = await _upsert_connection_health(
            db,
            account_id,
            effective_workspace,
            state=state,
            failure_category=failure_category,
            safe_message_code=safe_message_code,
            credential_revision=credential_revision,
            last_tested_at=last_tested_at,
            last_succeeded_at=last_succeeded_at,
        )
        await _audit(
            db,
            account_id,
            "health_updated",
            {
                "state": state,
                "failure_category": failure_category,
                "safe_message_code": safe_message_code,
            },
        )
        await db.commit()
    value["configured"] = bool(await configured_secret_types(account_id))
    value["enabled"] = account.get("status") == "active"
    return value


# The more explicit name reads well at provider call sites and keeps the
# shorter update helper available to existing integrations.
record_integration_health = update_integration_health
get_connection_health = get_integration_health
set_connection_health = update_integration_health


def _box() -> Fernet:
    encoded = os.getenv("AITOB_INTEGRATION_MASTER_KEY", "").strip()
    if not encoded:
        raise IntegrationSecretUnavailable("Integration credential master key is unavailable.")
    try:
        return Fernet(encoded.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise IntegrationSecretUnavailable("Integration credential master key is invalid.") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _audit(db: dbapi.Connection, account_id: str | None, action: str, detail: dict[str, Any] | None = None) -> None:
    # Integration audit rows are operational metadata, never a credential
    # sink.  Keep the existing table/API shape while dropping unsafe fields.
    await db.execute(
        "INSERT INTO integration_audit (account_id, action, detail_json) VALUES (?, ?, ?)",
        (account_id, action, json.dumps(_safe_audit_detail(detail or {}), sort_keys=True)),
    )


async def create_integration_account(
    workspace_id: str, provider_type: str, external_account_id: str, display_name: str,
    *, metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not all(isinstance(value, str) and value.strip() for value in (workspace_id, provider_type, external_account_id, display_name)):
        raise IntegrationError("Integration account identity is required.")
    provider_type = _validate_provider_type(provider_type)
    safe_metadata = _safe_metadata(metadata or {})
    account_id = str(uuid.uuid4())
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        await db.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (account_id, workspace_id.strip(), workspace_id.strip(), provider_type, external_account_id.strip(), display_name.strip(), json.dumps(safe_metadata, sort_keys=True)),
        )
        await _audit(db, account_id, "created", {"provider_type": provider_type})
        await db.commit()
        row = await (await db.execute("SELECT * FROM integration_accounts WHERE id=?", (account_id,))).fetchone()
    return _public_account(dict(row))


def _public_account(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "owner_id": row["owner_id"], "workspace_id": row.get("workspace_id"), "provider_type": row["provider_type"],
        "external_account_id": row["external_account_id"], "display_name": row["display_name"],
        "status": row["status"], "metadata": _safe_json_metadata(row.get("metadata_json")),
        "created_at": row.get("created_at"), "updated_at": row.get("updated_at"),
    }


async def get_integration_account(account_id: str, *, workspace_id: str | None = None, active_only: bool = True) -> dict[str, Any] | None:
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        clauses = ["id=?"]
        params: list[str] = [account_id]
        if workspace_id is not None:
            clauses.append("workspace_id=?")
            params.append(workspace_id)
        if active_only:
            clauses.append("status='active'")
        row = await (await db.execute(f"SELECT * FROM integration_accounts WHERE {' AND '.join(clauses)}", params)).fetchone()
    return _public_account(dict(row)) if row else None


async def update_integration_account(
    account_id: str,
    *,
    workspace_id: str,
    external_account_id: str | None = None,
    display_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update provider identity metadata after an OAuth callback.

    OAuth may discover the provider's real user id only after consent. Keep
    that identity and safe display metadata on the workspace-owned account;
    credentials remain in the encrypted credential table.
    """
    account = await get_integration_account(account_id, workspace_id=workspace_id, active_only=False)
    if not account:
        raise IntegrationError("Integration account is unavailable in this workspace.")
    fields: list[str] = []
    values: list[Any] = []
    if external_account_id is not None and external_account_id.strip():
        fields.append("external_account_id=?")
        values.append(external_account_id.strip())
    if display_name is not None and display_name.strip():
        fields.append("display_name=?")
        values.append(display_name.strip())
    if metadata is not None:
        fields.append("metadata_json=?")
        values.append(json.dumps(_safe_metadata(metadata), sort_keys=True))
    if fields:
        values.extend([account_id, workspace_id])
        async with dbapi.connect(_database_target()) as db:
            await db.execute(
                f"UPDATE integration_accounts SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND workspace_id=?",
                values,
            )
            await db.commit()
    updated = await get_integration_account(account_id, workspace_id=workspace_id, active_only=False)
    if not updated:
        raise IntegrationError("Integration account is unavailable in this workspace.")
    return updated


async def get_integration_workspace_id(account_id: str) -> str | None:
    """Resolve an integration owner's workspace without exposing credentials.

    Provider clients use this only for tenant-scoped telemetry/backoff records;
    callers still validate the tournament/account binding before doing provider
    work.  Returning ``None`` for an unbound legacy account keeps migration
    fixtures explicit instead of guessing an owner.
    """
    if not account_id:
        return None
    async with dbapi.connect(_database_target()) as db:
        row = await (await db.execute(
            "SELECT workspace_id FROM integration_accounts WHERE id=?",
            (account_id,),
        )).fetchone()
    return str(row[0]) if row and row[0] else None


async def list_integration_accounts(workspace_id: str | None) -> list[dict[str, Any]]:
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        if workspace_id is None:
            rows = await (await db.execute(
                "SELECT * FROM integration_accounts ORDER BY provider_type, display_name"
            )).fetchall()
        else:
            rows = await (await db.execute(
                "SELECT * FROM integration_accounts WHERE workspace_id=? ORDER BY provider_type, display_name",
                (workspace_id,),
            )).fetchall()
    return [_public_account(dict(row)) for row in rows]


async def set_integration_secret(
    owner_id: str,
    secret_type: str,
    secret: str,
    *,
    owner_kind: str = "account",
    workspace_id: str | None = None,
) -> int:
    """Encrypt and atomically replace a credential, returning its revision.

    The revision is the only credential lifecycle value exposed to internal
    health bookkeeping.  Ciphertext and plaintext never enter the returned
    value, audit detail, or public account projection.
    """
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise IntegrationError("Integration credential owner is required.")
    owner_kind = str(owner_kind or "").strip().lower()
    if owner_kind not in {"account", "application"}:
        raise IntegrationError("Unsupported integration credential owner.")
    secret_type = str(secret_type or "").strip().lower()
    if not secret_type or not isinstance(secret, str) or not secret.strip():
        raise IntegrationError("Empty secrets are not stored.")

    account = None
    if owner_kind == "account":
        account = await get_integration_account(
            owner_id.strip(), workspace_id=workspace_id, active_only=False
        )
        if not account:
            raise IntegrationError("Integration account is unavailable in this workspace.")
        provider_type = _validate_provider_type(account["provider_type"])
        expected_secret_types = {
            "gemini": {"api_key"},
            "openai": {"api_key"},
            "discord": {"bot_token", "access_token", "refresh_token"},
            "challonge": {"api_key", "access_token", "refresh_token"},
            "startgg": {"api_key", "access_token", "refresh_token"},
        }[provider_type]
        if secret_type not in expected_secret_types:
            raise IntegrationError("Unsupported credential type for integration provider.")
    elif secret_type != "client_secret":
        # OAuth applications currently use client_secret material only.  This
        # keeps an application row from becoming a generic secret bucket.
        raise IntegrationError("Unsupported OAuth application credential type.")

    cipher = _box().encrypt(secret.encode("utf-8")).decode("ascii")
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        cursor = await db.execute(
            """
            INSERT INTO integration_credentials
                (owner_kind, owner_id, secret_type, ciphertext,
                 credential_revision, updated_at)
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(owner_kind, owner_id, secret_type)
            DO UPDATE SET
                ciphertext=excluded.ciphertext,
                credential_revision=COALESCE(integration_credentials.credential_revision, 1) + 1,
                updated_at=excluded.updated_at
            RETURNING credential_revision
            """,
            (owner_kind, owner_id.strip(), secret_type, cipher, _now()),
        )
        revision_row = await cursor.fetchone()
        revision = int(revision_row[0]) if revision_row and revision_row[0] is not None else 1

        if account and account.get("workspace_id"):
            await _upsert_connection_health(
                db,
                owner_id.strip(),
                str(account["workspace_id"]),
                state=(
                    "configured_untested"
                    if account.get("status") == "active"
                    else "disabled"
                ),
                failure_category=None,
                safe_message_code="credential_saved",
                credential_revision=revision,
                # A replacement invalidates prior test evidence.
                last_tested_at=None,
                last_succeeded_at=None,
            )
        await _audit(
            db,
            owner_id if owner_kind == "account" else None,
            "credential_rotated",
            {"secret_type": secret_type, "owner_kind": owner_kind},
        )
        await db.commit()
    return revision


async def get_integration_secret(owner_id: str, secret_type: str, *, owner_kind: str = "account") -> str | None:
    async with dbapi.connect(_database_target()) as db:
        row = await (await db.execute(
            "SELECT ciphertext FROM integration_credentials WHERE owner_kind=? AND owner_id=? AND secret_type=?",
            (owner_kind, owner_id, secret_type),
        )).fetchone()
    if not row:
        return None
    try:
        return _box().decrypt(str(row[0]).encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise IntegrationSecretUnavailable("Integration credential cannot be authenticated.") from exc


async def configured_secret_types(owner_id: str, *, owner_kind: str = "account") -> set[str]:
    async with dbapi.connect(_database_target()) as db:
        rows = await (await db.execute(
            "SELECT secret_type FROM integration_credentials WHERE owner_kind=? AND owner_id=?", (owner_kind, owner_id)
        )).fetchall()
    return {str(row[0]) for row in rows}


async def get_integration_secret_revision(
    owner_id: str,
    secret_type: str,
    *,
    owner_kind: str = "account",
) -> int | None:
    """Return only the monotonic revision for a credential, never its value."""
    owner_kind = str(owner_kind or "").strip().lower()
    if owner_kind not in {"account", "application"}:
        raise IntegrationError("Unsupported integration credential owner.")
    async with dbapi.connect(_database_target()) as db:
        return await _credential_revision(
            db,
            owner_id,
            str(secret_type or "").strip().lower(),
            owner_kind=owner_kind,
        )


async def remove_integration_secret(
    owner_id: str,
    secret_type: str,
    *,
    owner_kind: str = "account",
    workspace_id: str | None = None,
) -> bool:
    """Delete credential ciphertext and degrade account health safely."""
    owner_kind = str(owner_kind or "").strip().lower()
    secret_type = str(secret_type or "").strip().lower()
    if owner_kind not in {"account", "application"}:
        raise IntegrationError("Unsupported integration credential owner.")
    if not owner_id or not secret_type:
        raise IntegrationError("Integration credential identity is required.")

    account = None
    if owner_kind == "account":
        account = await get_integration_account(
            owner_id, workspace_id=workspace_id, active_only=False
        )
        if not account:
            raise IntegrationError("Integration account is unavailable in this workspace.")
        _validate_provider_type(account["provider_type"])

    async with dbapi.connect(_database_target()) as db:
        prior_revision = await _credential_revision(
            db, owner_id, secret_type, owner_kind=owner_kind
        )
        cursor = await db.execute(
            "DELETE FROM integration_credentials WHERE owner_kind=? AND owner_id=? AND secret_type=?",
            (owner_kind, owner_id, secret_type),
        )
        removed = cursor.rowcount > 0
        if account and account.get("workspace_id") and removed:
            remaining = await _credential_revision(db, owner_id)
            next_state = (
                "disabled"
                if account.get("status") != "active"
                else ("configured_untested" if remaining is not None else "missing")
            )
            await _upsert_connection_health(
                db,
                owner_id,
                str(account["workspace_id"]),
                state=next_state,
                failure_category=(
                    None
                    if next_state in {"disabled", "configured_untested"}
                    else "missing_credential"
                ),
                safe_message_code="credential_removed",
                credential_revision=prior_revision,
                last_tested_at=None,
                last_succeeded_at=None,
            )
        if removed:
            await _audit(
                db,
                owner_id if owner_kind == "account" else None,
                "credential_removed",
                {"secret_type": secret_type, "owner_kind": owner_kind},
            )
        await db.commit()
    return removed


# API/domain callers commonly use the verb ``delete`` for credential removal;
# keep both names pointed at the same redaction-safe lifecycle operation.
delete_integration_secret = remove_integration_secret


async def add_integration_destination(account_id: str, destination_type: str, external_id: str, display_name: str = "", *, workspace_id: str | None = None) -> dict[str, Any]:
    account = await get_integration_account(account_id, workspace_id=workspace_id)
    if not account:
        raise IntegrationError("Active integration account was not found.")
    # Destinations inherit the account's durable owner.  A direct service
    # caller cannot accidentally create an unowned destination by omitting the
    # optional compatibility scope, and a supplied scope must match it.
    account_workspace = account.get("workspace_id")
    if account_workspace and workspace_id not in (None, account_workspace):
        raise IntegrationError("Integration account is unavailable in this workspace.")
    destination_workspace = account_workspace or workspace_id
    destination_id = str(uuid.uuid4())
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        await db.execute(
            "INSERT INTO integration_destinations (id, account_id, workspace_id, destination_type, external_id, display_name) VALUES (?, ?, ?, ?, ?, ?)",
            (destination_id, account_id, destination_workspace, destination_type, external_id, display_name),
        )
        await _audit(db, account_id, "destination_added", {"destination_type": destination_type})
        await db.commit()
        row = await (await db.execute("SELECT * FROM integration_destinations WHERE id=?", (destination_id,))).fetchone()
    return {key: row[key] for key in row.keys() if key != "external_id"} | {"configured": bool(row["external_id"])}


async def get_destination(account_id: str, destination_type: str, *, workspace_id: str | None = None) -> dict[str, Any] | None:
    account = await get_integration_account(account_id, workspace_id=workspace_id, active_only=False)
    if not account:
        return None
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        clauses = "account_id=? AND destination_type=? AND status='active'"
        params: list[str] = [account_id, destination_type]
        effective_workspace = account.get("workspace_id") or workspace_id
        if effective_workspace is not None:
            clauses += " AND workspace_id=?"; params.append(effective_workspace)
        row = await (await db.execute(
            f"SELECT * FROM integration_destinations WHERE {clauses} ORDER BY created_at DESC LIMIT 1",
            params,
        )).fetchone()
    return dict(row) if row else None


async def list_integration_destinations(account_id: str, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
    account = await get_integration_account(account_id, workspace_id=workspace_id, active_only=False)
    if not account:
        return []
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        clauses = "account_id=?"; params: list[str] = [account_id]
        effective_workspace = account.get("workspace_id") or workspace_id
        if effective_workspace is not None:
            clauses += " AND workspace_id=?"; params.append(effective_workspace)
        rows = await (await db.execute(
            f"SELECT id, account_id, destination_type, display_name, status, created_at FROM integration_destinations WHERE {clauses} ORDER BY destination_type, display_name",
            params,
        )).fetchall()
    return [dict(row) | {"configured": True} for row in rows]


async def create_oauth_application(owner_id: str, provider_type: str, client_id: str, redirect_uri: str, client_secret: str) -> dict[str, Any]:
    """Persist OAuth application material separately from every connected account."""
    if not all(isinstance(value, str) and value.strip() for value in (owner_id, provider_type, client_id, redirect_uri, client_secret)):
        raise IntegrationError("OAuth application fields are required.")
    app_id = str(uuid.uuid4())
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        existing = await (await db.execute(
            "SELECT * FROM integration_oauth_applications WHERE owner_id=? AND provider_type=? AND client_id=? AND redirect_uri=?",
            (owner_id, provider_type, client_id, redirect_uri),
        )).fetchone()
        if existing:
            app_id = str(existing["id"])
        else:
            await db.execute(
                "INSERT INTO integration_oauth_applications (id, owner_id, provider_type, client_id, redirect_uri) VALUES (?, ?, ?, ?, ?)",
                (app_id, owner_id, provider_type, client_id, redirect_uri),
            )
        await db.commit()
    await set_integration_secret(app_id, "client_secret", client_secret, owner_kind="application")
    return {"id": app_id, "owner_id": owner_id, "provider_type": provider_type, "client_id": client_id, "redirect_uri": redirect_uri, "configured": True}


async def get_oauth_application(application_id: str) -> dict[str, Any] | None:
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        row = await (await db.execute("SELECT * FROM integration_oauth_applications WHERE id=? AND status='active'", (application_id,))).fetchone()
    if not row:
        return None
    value = dict(row)
    value["configured"] = "client_secret" in await configured_secret_types(application_id, owner_kind="application")
    return value


async def get_challonge_credential(account_id: str, secret_type: str) -> str | None:
    account = await get_integration_account(account_id)
    if not account or account["provider_type"] != "challonge":
        raise IntegrationSecretUnavailable("Challonge account is unavailable.")
    return await get_integration_secret(account_id, secret_type)


async def get_challonge_oauth_application(account_id: str) -> dict[str, Any] | None:
    account = await get_integration_account(account_id)
    if not account or account["provider_type"] != "challonge":
        return None
    application_id = str(account["metadata"].get("oauth_application_id") or "")
    return await get_oauth_application(application_id) if application_id else None


async def get_discord_credential(account_id: str) -> str | None:
    account = await get_integration_account(account_id)
    if not account or account["provider_type"] != "discord":
        raise IntegrationSecretUnavailable("Discord account is unavailable.")
    return await get_integration_secret(account_id, "bot_token")


async def disable_integration_account(account_id: str, *, workspace_id: str | None = None) -> None:
    async with dbapi.connect(_database_target()) as db:
        account = await get_integration_account(account_id, workspace_id=workspace_id, active_only=False)
        if not account:
            raise IntegrationError("Integration account is unavailable in this workspace.")
        active = await (await db.execute(
            "SELECT COUNT(*) FROM tournaments WHERE provider_account_id=? AND (workspace_id=? OR workspace_id IS NULL) AND COALESCE(provider_sync_status, 'ready') NOT IN ('archived', 'complete')",
            (account_id, account["workspace_id"]),
        )).fetchone()
        if active and active[0]:
            raise IntegrationAccountInUse("An active tournament still uses this integration account.")
        await db.execute("UPDATE integration_accounts SET status='disabled', updated_at=? WHERE id=? AND workspace_id=?", (_now(), account_id, account["workspace_id"]))
        if account.get("workspace_id"):
            await db.execute(
                """
                UPDATE integration_connection_health
                SET state='disabled', failure_category=NULL,
                    safe_message_code='account_disabled', updated_at=?
                WHERE account_id=? AND workspace_id=?
                """,
                (_now(), account_id, account["workspace_id"]),
            )
        await _audit(db, account_id, "disabled")
        await db.commit()


async def enable_integration_account(
    account_id: str,
    *,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Re-enable an account while preserving health and credential history."""
    account = await get_integration_account(
        account_id, workspace_id=workspace_id, active_only=False
    )
    if not account:
        raise IntegrationError("Integration account is unavailable in this workspace.")
    _validate_provider_type(account["provider_type"])
    effective_workspace = account.get("workspace_id") or workspace_id
    if not effective_workspace:
        raise IntegrationError("Integration account has no workspace owner.")
    async with dbapi.connect(_database_target()) as db:
        db.row_factory = dbapi.Row
        await db.execute(
            "UPDATE integration_accounts SET status='active', updated_at=? WHERE id=? AND workspace_id=?",
            (_now(), account_id, effective_workspace),
        )
        revision = await _credential_revision(db, account_id)
        value = await _upsert_connection_health(
            db,
            account_id,
            str(effective_workspace),
            state="configured_untested" if revision is not None else "missing",
            failure_category=None if revision is not None else "missing_credential",
            safe_message_code="account_enabled",
            credential_revision=revision,
            last_tested_at=None,
            last_succeeded_at=None,
        )
        await _audit(db, account_id, "enabled")
        await db.commit()
    value["configured"] = revision is not None
    value["enabled"] = True
    return value


async def _legacy_value(db: dbapi.Connection, table: str, key: str) -> str | None:
    row = await (await db.execute(f"SELECT value FROM {table} WHERE key=?", (key,))).fetchone()
    return str(row[0]) if row and row[0] else None


async def _legacy_account(db: dbapi.Connection, provider_type: str, workspace_id: str) -> str | None:
    row = await (await db.execute(
        "SELECT id FROM integration_accounts WHERE provider_type=? AND external_account_id='legacy' AND workspace_id=?", (provider_type, workspace_id)
    )).fetchone()
    return str(row[0]) if row else None


async def migrate_legacy_integrations(workspace_id: str) -> dict[str, Any]:
    """Copy legacy settings into encrypted account storage; never delete originals."""
    _box()  # Fail before starting a transaction.
    if not workspace_id:
        raise IntegrationError("An explicit workspace is required for legacy integration migration.")
    report: dict[str, Any] = {
        "migrated_accounts": 0,
        "discord_account_id": None,
        "challonge_account_id": None,
        "startgg_account_id": None,
        "oauth_application_id": None,
        "legacy_retained": True,
    }
    async with dbapi.connect(_database_target()) as db:
        await db.execute("BEGIN")
        discord_token = await _legacy_value(db, "global_settings", "DISCORD_BOT_TOKEN") or await _legacy_value(db, "connections", "DISCORD_BOT_TOKEN")
        channel = await _legacy_value(db, "connections", "MATCH_CALL_CHANNEL_ID") or await _legacy_value(db, "global_settings", "MATCH_CALL_CHANNEL_ID")
        access = await _legacy_value(db, "connections", "CHALLONGE_OAUTH_ACCESS_TOKEN")
        api_key = await _legacy_value(db, "connections", "CHALLONGE_API_KEY")
        startgg_token = await _legacy_value(db, "global_settings", "STARTGG_API_TOKEN") or await _legacy_value(db, "connections", "STARTGG_API_TOKEN")
        if discord_token:
            account = await _legacy_account(db, "discord", workspace_id)
            if not account:
                account = str(uuid.uuid4())
                await db.execute("INSERT INTO integration_accounts (id, owner_id, workspace_id, provider_type, external_account_id, display_name) VALUES (?, ?, ?, 'discord', 'legacy', 'Migrated Discord')", (account, workspace_id, workspace_id))
                report["migrated_accounts"] += 1
            report["discord_account_id"] = account
            cipher = _box().encrypt(discord_token.encode()).decode()
            await db.execute("INSERT INTO integration_credentials (owner_kind, owner_id, secret_type, ciphertext, updated_at) VALUES ('account', ?, 'bot_token', ?, ?) ON CONFLICT(owner_kind, owner_id, secret_type) DO NOTHING", (account, cipher, _now()))
            if channel:
                await db.execute("INSERT INTO integration_destinations (id, account_id, workspace_id, destination_type, external_id, display_name) SELECT ?, ?, ?, 'match_call_channel', ?, 'Migrated channel' WHERE NOT EXISTS (SELECT 1 FROM integration_destinations WHERE account_id=? AND destination_type='match_call_channel' AND external_id=?)", (str(uuid.uuid4()), account, workspace_id, channel, account, channel))
            await _audit(db, account, "legacy_migrated", {"provider_type": "discord"})
            await db.execute("UPDATE tournaments SET discord_account_id=? WHERE workspace_id=? AND (discord_account_id IS NULL OR discord_account_id='')", (account, workspace_id))
        if access or api_key:
            account = await _legacy_account(db, "challonge", workspace_id)
            if not account:
                account = str(uuid.uuid4())
                await db.execute("INSERT INTO integration_accounts (id, owner_id, workspace_id, provider_type, external_account_id, display_name) VALUES (?, ?, ?, 'challonge', 'legacy', 'Migrated Challonge')", (account, workspace_id, workspace_id))
                report["migrated_accounts"] += 1
            report["challonge_account_id"] = account
            for name, value in (("access_token", access), ("api_key", api_key), ("refresh_token", await _legacy_value(db, "connections", "CHALLONGE_OAUTH_REFRESH_TOKEN"))):
                if value:
                    await db.execute("INSERT INTO integration_credentials (owner_kind, owner_id, secret_type, ciphertext, updated_at) VALUES ('account', ?, ?, ?, ?) ON CONFLICT(owner_kind, owner_id, secret_type) DO NOTHING", (account, name, _box().encrypt(value.encode()).decode(), _now()))
            await db.execute("UPDATE tournaments SET provider_account_id=? WHERE workspace_id=? AND provider_type='challonge' AND (provider_account_id IS NULL OR provider_account_id='' OR provider_account_id='default')", (account, workspace_id))
            await _audit(db, account, "legacy_migrated", {"provider_type": "challonge"})
        if startgg_token:
            account = await _legacy_account(db, "startgg", workspace_id)
            if not account:
                account = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO integration_accounts (id, owner_id, workspace_id, provider_type, external_account_id, display_name) VALUES (?, ?, ?, 'startgg', 'legacy', 'Migrated Start.gg')",
                    (account, workspace_id, workspace_id),
                )
                report["migrated_accounts"] += 1
            report["startgg_account_id"] = account
            await db.execute(
                "INSERT INTO integration_credentials (owner_kind, owner_id, secret_type, ciphertext, updated_at) VALUES ('account', ?, 'access_token', ?, ?) ON CONFLICT(owner_kind, owner_id, secret_type) DO NOTHING",
                (account, _box().encrypt(startgg_token.encode()).decode(), _now()),
            )
            await db.execute(
                "UPDATE tournaments SET provider_account_id=? WHERE workspace_id=? AND provider_type='startgg' AND (provider_account_id IS NULL OR provider_account_id='' OR provider_account_id='default')",
                (account, workspace_id),
            )
            await _audit(db, account, "legacy_migrated", {"provider_type": "startgg"})
        client_id = await _legacy_value(db, "connections", "CHALLONGE_OAUTH_CLIENT_ID")
        callback = await _legacy_value(db, "connections", "CHALLONGE_OAUTH_REDIRECT_URI")
        client_secret = await _legacy_value(db, "connections", "CHALLONGE_OAUTH_CLIENT_SECRET")
        if client_id and callback and client_secret:
            existing = await (await db.execute("SELECT id FROM integration_oauth_applications WHERE owner_id=? AND provider_type='challonge' AND client_id=? AND redirect_uri=?", (workspace_id, client_id, callback))).fetchone()
            app_id = str(existing[0]) if existing else str(uuid.uuid4())
            if not existing:
                await db.execute("INSERT INTO integration_oauth_applications (id, owner_id, provider_type, client_id, redirect_uri) VALUES (?, ?, 'challonge', ?, ?)", (app_id, workspace_id, client_id, callback))
            await db.execute("INSERT INTO integration_credentials (owner_kind, owner_id, secret_type, ciphertext, updated_at) VALUES ('application', ?, 'client_secret', ?, ?) ON CONFLICT(owner_kind, owner_id, secret_type) DO NOTHING", (app_id, _box().encrypt(client_secret.encode()).decode(), _now()))
            report["oauth_application_id"] = app_id
            if report["challonge_account_id"]:
                await db.execute("UPDATE integration_accounts SET metadata_json=?, updated_at=? WHERE id=?", (json.dumps({"oauth_application_id": app_id}), _now(), report["challonge_account_id"]))
        await db.commit()
    return report
