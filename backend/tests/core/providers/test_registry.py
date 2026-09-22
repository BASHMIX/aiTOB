from unittest.mock import AsyncMock

import pytest

from backend.core.providers.registry import (
    ProviderRegistry,
    get_provider_for_account,
    get_provider_for_tournament,
    provider_registry,
    shutdown_providers,
)
from backend.core.providers.startgg import StartGGProvider


@pytest.fixture(autouse=True)
def clear_registry_instances():
    provider_registry.clear_for_tests()
    yield
    provider_registry.clear_for_tests()


def test_local_registry_rejects_unknown_provider():
    registry = ProviderRegistry()
    with pytest.raises(ValueError, match="Unknown provider: custom"):
        registry.resolve("custom", workspace_id="workspace-a", account_id="account-a")


@pytest.mark.asyncio
async def test_account_resolution_is_scoped_and_cached(monkeypatch):
    account_lookup = AsyncMock(return_value={
        "id": "account-a", "workspace_id": "workspace-a",
        "provider_type": "startgg", "status": "active",
    })
    monkeypatch.setattr("backend.core.integrations.get_integration_account", account_lookup)

    first = await get_provider_for_account("startgg", "account-a", "workspace-a")
    second = await get_provider_for_account("startgg", "account-a", "workspace-a")

    assert isinstance(first, StartGGProvider)
    assert first is second
    assert first._client.provider_account_id == "account-a"
    assert account_lookup.await_count == 2


@pytest.mark.asyncio
async def test_account_resolution_rejects_foreign_or_disabled_account(monkeypatch):
    monkeypatch.setattr(
        "backend.core.integrations.get_integration_account", AsyncMock(return_value=None)
    )
    with pytest.raises(ValueError, match="not available in this workspace"):
        await get_provider_for_account("startgg", "foreign", "workspace-a")


@pytest.mark.asyncio
async def test_tournament_resolution_requires_workspace_binding(monkeypatch):
    from backend.core import database

    monkeypatch.setattr(database, "get_tournament", AsyncMock(return_value={
        "slug": "owned/event", "provider_type": "startgg",
        "workspace_id": "workspace-a", "provider_account_id": None,
    }))
    with pytest.raises(ValueError, match="not bound to an integration account"):
        await get_provider_for_tournament("owned/event", "workspace-a")


@pytest.mark.asyncio
async def test_tournament_resolution_uses_selected_account(monkeypatch):
    from backend.core import database

    monkeypatch.setattr(database, "get_tournament", AsyncMock(return_value={
        "slug": "owned/event", "provider_type": "startgg",
        "workspace_id": "workspace-a", "provider_account_id": "account-a",
    }))
    monkeypatch.setattr(
        "backend.core.integrations.get_integration_account",
        AsyncMock(return_value={
            "id": "account-a", "workspace_id": "workspace-a",
            "provider_type": "startgg", "status": "active",
        }),
    )

    provider = await get_provider_for_tournament("owned/event", "workspace-a")
    assert isinstance(provider, StartGGProvider)
    assert provider._client.provider_account_id == "account-a"


@pytest.mark.asyncio
async def test_shutdown_closes_account_scoped_instances(monkeypatch):
    monkeypatch.setattr(
        "backend.core.integrations.get_integration_account",
        AsyncMock(return_value={
            "id": "account-a", "workspace_id": "workspace-a",
            "provider_type": "startgg", "status": "active",
        }),
    )
    provider = await get_provider_for_account("startgg", "account-a", "workspace-a")
    provider.close = AsyncMock()

    await shutdown_providers()

    provider.close.assert_awaited_once()
