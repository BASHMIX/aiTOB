"""Runtime bot identity must be explicitly owned by one workspace."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_selected_account_lookup_is_workspace_scoped(monkeypatch):
    from backend.bot import main
    from backend.core import integrations

    monkeypatch.setenv("AITOB_DISCORD_ACCOUNT_ID", "discord-a")
    monkeypatch.setenv("AITOB_DISCORD_WORKSPACE_ID", "workspace-a")
    monkeypatch.setattr(main, "init_db", AsyncMock())
    account_lookup = AsyncMock(return_value={
        "id": "discord-a", "provider_type": "discord", "status": "active",
    })
    list_accounts = AsyncMock(side_effect=AssertionError("runtime must not enumerate global accounts"))
    workspace_lookup = AsyncMock(return_value="workspace-a")
    credential_lookup = AsyncMock(return_value="token-not-asserted")
    monkeypatch.setattr(integrations, "get_integration_account", account_lookup)
    monkeypatch.setattr(integrations, "list_integration_accounts", list_accounts)
    monkeypatch.setattr(integrations, "get_integration_workspace_id", workspace_lookup)
    monkeypatch.setattr(integrations, "get_discord_credential", credential_lookup)

    account_id, token, workspace_id = await main.load_discord_account_token()

    assert (account_id, token, workspace_id) == ("discord-a", "token-not-asserted", "workspace-a")
    account_lookup.assert_awaited_once_with("discord-a", workspace_id="workspace-a", active_only=True)
    list_accounts.assert_not_awaited()


@pytest.mark.asyncio
async def test_unselected_bot_requires_explicit_workspace(monkeypatch):
    from backend.bot import main
    from backend.core import integrations

    monkeypatch.delenv("AITOB_DISCORD_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("AITOB_DISCORD_WORKSPACE_ID", raising=False)
    monkeypatch.setattr(main, "init_db", AsyncMock())
    list_accounts = AsyncMock(side_effect=AssertionError("global account enumeration is forbidden"))
    monkeypatch.setattr(integrations, "list_integration_accounts", list_accounts)

    with pytest.raises(RuntimeError, match="AITOB_DISCORD_WORKSPACE_ID is required"):
        await main.load_discord_account_token()
    list_accounts.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_verification_cannot_cross_workspace():
    from backend.core import database
    from backend.core.database import (
        create_pending_verification,
        get_pending_verification,
    )

    await database.init_db()
    await create_pending_verification(
        "discord-verification", "profile-a", "CODE-A", workspace_id="workspace-a",
    )
    assert await get_pending_verification("discord-verification", "workspace-a")
    assert await get_pending_verification("discord-verification", "workspace-b") is None
