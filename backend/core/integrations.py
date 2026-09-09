"""Account-scoped external integrations and encrypted credential storage.

No caller may fall back to a global provider secret.  A missing service master key
or malformed ciphertext is deliberately a hard configuration failure.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.core.storage import dbapi as aiosqlite
from cryptography.fernet import Fernet, InvalidToken

from backend.core import database


def _db_path() -> str:
    """Resolve at call time so test/acceptance contexts never share production DB."""
    return database.DB_PATH


class IntegrationError(RuntimeError):
    pass


class IntegrationSecretUnavailable(IntegrationError):
    pass


class IntegrationAccountInUse(IntegrationError):
    pass


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


async def _audit(db: aiosqlite.Connection, account_id: str | None, action: str, detail: dict[str, Any] | None = None) -> None:
    await db.execute(
        "INSERT INTO integration_audit (account_id, action, detail_json) VALUES (?, ?, ?)",
        (account_id, action, json.dumps(detail or {}, sort_keys=True)),
    )


async def create_integration_account(
    workspace_id: str, provider_type: str, external_account_id: str, display_name: str,
    *, metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not all(isinstance(value, str) and value.strip() for value in (workspace_id, provider_type, external_account_id, display_name)):
        raise IntegrationError("Integration account identity is required.")
    account_id = str(uuid.uuid4())
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (account_id, workspace_id.strip(), workspace_id.strip(), provider_type.strip(), external_account_id.strip(), display_name.strip(), json.dumps(metadata or {}, sort_keys=True)),
        )
        await _audit(db, account_id, "created", {"provider_type": provider_type})
        await db.commit()
        row = await (await db.execute("SELECT * FROM integration_accounts WHERE id=?", (account_id,))).fetchone()
    return _public_account(dict(row))


def _public_account(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "owner_id": row["owner_id"], "workspace_id": row.get("workspace_id"), "provider_type": row["provider_type"],
        "external_account_id": row["external_account_id"], "display_name": row["display_name"],
        "status": row["status"], "metadata": json.loads(row.get("metadata_json") or "{}"),
        "created_at": row.get("created_at"), "updated_at": row.get("updated_at"),
    }


async def get_integration_account(account_id: str, *, workspace_id: str | None = None, active_only: bool = True) -> dict[str, Any] | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        clauses = ["id=?"]
        params: list[str] = [account_id]
        if workspace_id is not None:
            clauses.append("workspace_id=?")
            params.append(workspace_id)
        if active_only:
            clauses.append("status='active'")
        row = await (await db.execute(f"SELECT * FROM integration_accounts WHERE {' AND '.join(clauses)}", params)).fetchone()
    return _public_account(dict(row)) if row else None


async def get_integration_workspace_id(account_id: str) -> str | None:
    """Resolve an integration owner's workspace without exposing credentials.

    Provider clients use this only for tenant-scoped telemetry/backoff records;
    callers still validate the tournament/account binding before doing provider
    work.  Returning ``None`` for an unbound legacy account keeps migration
    fixtures explicit instead of guessing an owner.
    """
    if not account_id:
        return None
    async with aiosqlite.connect(_db_path()) as db:
        row = await (await db.execute(
            "SELECT workspace_id FROM integration_accounts WHERE id=?",
            (account_id,),
        )).fetchone()
    return str(row[0]) if row and row[0] else None


async def list_integration_accounts(workspace_id: str | None) -> list[dict[str, Any]]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
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


async def set_integration_secret(owner_id: str, secret_type: str, secret: str, *, owner_kind: str = "account", workspace_id: str | None = None) -> None:
    if not secret:
        raise IntegrationError("Empty secrets are not stored.")
    cipher = _box().encrypt(secret.encode("utf-8")).decode("ascii")
    if owner_kind == "account" and workspace_id is not None and not await get_integration_account(owner_id, workspace_id=workspace_id):
        raise IntegrationError("Integration account is unavailable in this workspace.")
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            """INSERT INTO integration_credentials (owner_kind, owner_id, secret_type, ciphertext, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(owner_kind, owner_id, secret_type)
               DO UPDATE SET ciphertext=excluded.ciphertext, updated_at=excluded.updated_at""",
            (owner_kind, owner_id, secret_type, cipher, _now()),
        )
        await _audit(db, owner_id if owner_kind == "account" else None, "credential_rotated", {"secret_type": secret_type, "owner_kind": owner_kind})
        await db.commit()


async def get_integration_secret(owner_id: str, secret_type: str, *, owner_kind: str = "account") -> str | None:
    async with aiosqlite.connect(_db_path()) as db:
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
    async with aiosqlite.connect(_db_path()) as db:
        rows = await (await db.execute(
            "SELECT secret_type FROM integration_credentials WHERE owner_kind=? AND owner_id=?", (owner_kind, owner_id)
        )).fetchall()
    return {str(row[0]) for row in rows}


async def add_integration_destination(account_id: str, destination_type: str, external_id: str, display_name: str = "", *, workspace_id: str | None = None) -> dict[str, Any]:
    if not await get_integration_account(account_id, workspace_id=workspace_id):
        raise IntegrationError("Active integration account was not found.")
    destination_id = str(uuid.uuid4())
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT INTO integration_destinations (id, account_id, workspace_id, destination_type, external_id, display_name) VALUES (?, ?, ?, ?, ?, ?)",
            (destination_id, account_id, workspace_id, destination_type, external_id, display_name),
        )
        await _audit(db, account_id, "destination_added", {"destination_type": destination_type})
        await db.commit()
        row = await (await db.execute("SELECT * FROM integration_destinations WHERE id=?", (destination_id,))).fetchone()
    return {key: row[key] for key in row.keys() if key != "external_id"} | {"configured": bool(row["external_id"])}


async def get_destination(account_id: str, destination_type: str, *, workspace_id: str | None = None) -> dict[str, Any] | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        clauses = "account_id=? AND destination_type=? AND status='active'"
        params: list[str] = [account_id, destination_type]
        if workspace_id is not None:
            clauses += " AND workspace_id=?"; params.append(workspace_id)
        row = await (await db.execute(
            f"SELECT * FROM integration_destinations WHERE {clauses} ORDER BY created_at DESC LIMIT 1",
            params,
        )).fetchone()
    return dict(row) if row else None


async def list_integration_destinations(account_id: str, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        clauses = "account_id=?"; params: list[str] = [account_id]
        if workspace_id is not None:
            clauses += " AND workspace_id=?"; params.append(workspace_id)
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
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
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
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
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
    async with aiosqlite.connect(_db_path()) as db:
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
        await _audit(db, account_id, "disabled")
        await db.commit()


async def _legacy_value(db: aiosqlite.Connection, table: str, key: str) -> str | None:
    row = await (await db.execute(f"SELECT value FROM {table} WHERE key=?", (key,))).fetchone()
    return str(row[0]) if row and row[0] else None


async def _legacy_account(db: aiosqlite.Connection, provider_type: str, workspace_id: str) -> str | None:
    row = await (await db.execute(
        "SELECT id FROM integration_accounts WHERE provider_type=? AND external_account_id='legacy' AND workspace_id=?", (provider_type, workspace_id)
    )).fetchone()
    return str(row[0]) if row else None


async def migrate_legacy_integrations(workspace_id: str) -> dict[str, Any]:
    """Copy legacy settings into encrypted account storage; never delete originals."""
    _box()  # Fail before starting a transaction.
    if not workspace_id:
        raise IntegrationError("An explicit workspace is required for legacy integration migration.")
    report: dict[str, Any] = {"migrated_accounts": 0, "discord_account_id": None, "challonge_account_id": None, "oauth_application_id": None, "legacy_retained": True}
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("BEGIN IMMEDIATE")
        discord_token = await _legacy_value(db, "global_settings", "DISCORD_BOT_TOKEN") or await _legacy_value(db, "connections", "DISCORD_BOT_TOKEN")
        channel = await _legacy_value(db, "connections", "MATCH_CALL_CHANNEL_ID") or await _legacy_value(db, "global_settings", "MATCH_CALL_CHANNEL_ID")
        access = await _legacy_value(db, "connections", "CHALLONGE_OAUTH_ACCESS_TOKEN")
        api_key = await _legacy_value(db, "connections", "CHALLONGE_API_KEY")
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
