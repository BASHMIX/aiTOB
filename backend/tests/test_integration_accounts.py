"""Security boundary tests for account-scoped integration credentials."""
from __future__ import annotations

import os

from backend.core.storage import dbapi as aiosqlite
import pytest

from backend.core import database


@pytest.fixture
async def integration_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "integrations.sqlite"))
    monkeypatch.setenv("AITOB_INTEGRATION_MASTER_KEY", "7lXNrOpw2HnqGYiRkqzGN70KGyxoDpcQ0H3jDXiVlvc=")
    await database.init_db()
    yield database.DB_PATH


@pytest.mark.asyncio
async def test_account_secrets_are_encrypted_and_isolated(integration_db):
    from backend.core.integrations import (
        create_integration_account,
        get_integration_secret,
        set_integration_secret,
    )

    first = await create_integration_account("admin", "challonge", "one", "Test one")
    second = await create_integration_account("admin", "challonge", "two", "Test two")
    await set_integration_secret(first["id"], "access_token", "first-secret")
    await set_integration_secret(second["id"], "access_token", "second-secret")

    assert await get_integration_secret(first["id"], "access_token") == "first-secret"
    assert await get_integration_secret(second["id"], "access_token") == "second-secret"
    async with aiosqlite.connect(integration_db) as db:
        row = await (await db.execute(
            "SELECT ciphertext FROM integration_credentials WHERE owner_id=?", (first["id"],)
        )).fetchone()
    assert row[0] != "first-secret"
    assert "first-secret" not in row[0]


@pytest.mark.asyncio
async def test_missing_master_key_fails_closed(integration_db, monkeypatch):
    from backend.core.integrations import IntegrationSecretUnavailable, create_integration_account, set_integration_secret

    account = await create_integration_account("admin", "discord", "bot", "Test bot")
    monkeypatch.delenv("AITOB_INTEGRATION_MASTER_KEY")
    with pytest.raises(IntegrationSecretUnavailable):
        await set_integration_secret(account["id"], "bot_token", "never-stored")


@pytest.mark.asyncio
async def test_legacy_migration_is_idempotent_and_preserves_plaintext_until_explicit_purge(integration_db):
    from backend.core.integrations import get_integration_secret, migrate_legacy_integrations

    await database.set_setting("DISCORD_BOT_TOKEN", "legacy-discord-token")
    await database.set_connection("MATCH_CALL_CHANNEL_ID", "safe-channel-id")
    await database.set_connection("CHALLONGE_OAUTH_ACCESS_TOKEN", "legacy-challonge-token")

    first = await migrate_legacy_integrations("admin")
    second = await migrate_legacy_integrations("admin")
    assert first["migrated_accounts"] == 2
    assert second["migrated_accounts"] == 0
    assert await get_integration_secret(first["discord_account_id"], "bot_token") == "legacy-discord-token"
    assert await get_integration_secret(first["challonge_account_id"], "access_token") == "legacy-challonge-token"
    assert await database.get_setting("DISCORD_BOT_TOKEN") == "legacy-discord-token"
    assert await database.get_connection("CHALLONGE_OAUTH_ACCESS_TOKEN") == "legacy-challonge-token"


@pytest.mark.asyncio
async def test_active_tournament_prevents_account_disable_or_delete(integration_db):
    from backend.core.integrations import (
        IntegrationAccountInUse,
        create_integration_account,
        disable_integration_account,
    )

    account = await create_integration_account("admin", "challonge", "test", "Test")
    await database.upsert_tournament(
        "challonge:test", "Test", "", "", "", "{}", provider_type="challonge",
        provider_tournament_id="1", provider_account_id=account["id"],
    )
    with pytest.raises(IntegrationAccountInUse):
        await disable_integration_account(account["id"])


@pytest.mark.asyncio
async def test_runtime_can_list_active_accounts_across_explicit_owners(integration_db):
    """A selected bot process must see the account bound to its acceptance DB."""
    from backend.core.integrations import create_integration_account, list_integration_accounts

    admin = await create_integration_account("admin", "discord", "admin-bot", "Admin Bot")
    acceptance = await create_integration_account("acceptance", "discord", "acceptance-bot", "Acceptance Bot")

    assert [account["id"] for account in await list_integration_accounts("admin")] == [admin["id"]]
    assert {account["id"] for account in await list_integration_accounts(None)} == {admin["id"], acceptance["id"]}


@pytest.mark.asyncio
async def test_workspace_account_lookup_and_secret_rotation_cannot_cross_scope(integration_db):
    from backend.core.integrations import (
        IntegrationError, create_integration_account, get_integration_account,
        set_integration_secret,
    )

    account = await create_integration_account("workspace-a", "discord", "bot-a", "Workspace A Bot")
    assert await get_integration_account(account["id"], workspace_id="workspace-b") is None
    with pytest.raises(IntegrationError, match="unavailable in this workspace"):
        await set_integration_secret(account["id"], "bot_token", "safe-test-value", workspace_id="workspace-b")
    await set_integration_secret(account["id"], "bot_token", "safe-test-value", workspace_id="workspace-a")


@pytest.mark.asyncio
async def test_legacy_migration_does_not_reuse_another_workspaces_account(integration_db):
    from backend.core.integrations import create_integration_account, migrate_legacy_integrations, get_integration_account
    other = await create_integration_account("other", "challonge", "legacy", "Other")
    await database.set_connection("CHALLONGE_OAUTH_ACCESS_TOKEN", "migration-test-token")
    async with aiosqlite.connect(integration_db) as db:
        for scope in ("admin", "other"):
            await db.execute("INSERT INTO tournaments (slug, name, provider_type, workspace_id) VALUES (?, ?, 'challonge', ?)", (scope, scope, scope))
        await db.commit()
    report = await migrate_legacy_integrations("admin")
    assert report["challonge_account_id"] != other["id"]
    assert (await get_integration_account(report["challonge_account_id"]))["workspace_id"] == "admin"
    assert (await database.get_tournament("other"))["provider_account_id"] is None


@pytest.mark.asyncio
async def test_legacy_startgg_credential_migrates_to_owner_account(integration_db):
    from backend.core.integrations import get_integration_secret, migrate_legacy_integrations

    await database.set_setting("STARTGG_API_TOKEN", "legacy-startgg-token")
    await database.upsert_tournament(
        "tournament/owner-startgg", "Owner Start.gg", "", "", "", "{}",
        provider_type="startgg", provider_tournament_id="owner-startgg",
        workspace_id="admin",
    )
    first = await migrate_legacy_integrations("admin")
    second = await migrate_legacy_integrations("admin")

    assert first["startgg_account_id"]
    assert second["startgg_account_id"] == first["startgg_account_id"]
    assert second["migrated_accounts"] == 0
    assert await get_integration_secret(first["startgg_account_id"], "access_token") == "legacy-startgg-token"
    assert (await database.get_tournament("tournament/owner-startgg"))["provider_account_id"] == first["startgg_account_id"]
