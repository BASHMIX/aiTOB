"""Canonical Start.gg reads always pass through the coordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.core.contracts import (
    ProviderSet,
    ProviderSetState,
    ProviderSnapshotRequestV2,
    ProviderSnapshotV2,
)
from backend.core.provider_sync_manager import ProviderSyncManager


class _StartGGReadFixture:
    provider_type = "startgg"

    async def fetch_snapshot(self, request: ProviderSnapshotRequestV2) -> ProviderSnapshotV2:
        return ProviderSnapshotV2(
            request=request,
            payload={"sets": [ProviderSet(id="set-1", state=ProviderSetState.CALLED)]},
        )


def _tournament(**overrides):
    return {
        "slug": "fixture",
        "workspace_id": "workspace-a",
        "provider_type": "startgg",
        "provider_account_id": "account-a",
        **overrides,
    }


@pytest.mark.asyncio
async def test_canonical_read_keeps_local_projection_shape(monkeypatch):
    from backend.core import provider_sync_manager as module

    provider = _StartGGReadFixture()
    sync_active_matches = AsyncMock()
    save_snapshot = AsyncMock()
    monkeypatch.setattr(module, "get_tournament", AsyncMock(return_value=_tournament()))
    monkeypatch.setattr(module, "get_provider_for_tournament", AsyncMock(return_value=provider))
    monkeypatch.setattr(module, "sync_active_matches", sync_active_matches)
    monkeypatch.setattr(module, "save_bracket_snapshot", save_snapshot)
    monkeypatch.setattr(module, "set_tournament_sync_status", AsyncMock())

    manager = ProviderSyncManager()
    result = await manager.sync_bracket("fixture", workspace_id="workspace-a")

    assert result["reason"] == "manual"
    assert result["sets"][0]["id"] == "set-1"
    assert result["sets"][0]["aitob_state"] == "called"
    sync_active_matches.assert_awaited_once()
    save_snapshot.assert_awaited_once_with("fixture", result["sets"], "workspace-a")
    assert manager._coordinator is not None


@pytest.mark.asyncio
async def test_canonical_read_uses_bound_account_and_workspace(monkeypatch):
    from backend.core import provider_sync_manager as module

    received_requests = []

    class CapturingProvider(_StartGGReadFixture):
        async def fetch_snapshot(self, request):
            received_requests.append(request)
            return await super().fetch_snapshot(request)

    provider_lookup = AsyncMock(return_value=CapturingProvider())
    monkeypatch.setattr(module, "get_tournament", AsyncMock(return_value=_tournament()))
    monkeypatch.setattr(module, "get_provider_for_tournament", provider_lookup)
    monkeypatch.setattr(module, "sync_active_matches", AsyncMock())
    monkeypatch.setattr(module, "save_bracket_snapshot", AsyncMock())
    monkeypatch.setattr(module, "set_tournament_sync_status", AsyncMock())

    await ProviderSyncManager().sync_bracket("fixture", workspace_id="workspace-a")

    provider_lookup.assert_awaited_once_with("fixture", "workspace-a")
    assert [request.provider_account_id for request in received_requests] == ["account-a"]


@pytest.mark.asyncio
async def test_unbound_tournament_fails_before_provider_resolution(monkeypatch):
    from backend.core import provider_sync_manager as module

    provider_lookup = AsyncMock(side_effect=AssertionError("provider must not be resolved"))
    monkeypatch.setattr(
        module, "get_tournament",
        AsyncMock(return_value=_tournament(provider_account_id=None)),
    )
    monkeypatch.setattr(module, "get_provider_for_tournament", provider_lookup)
    monkeypatch.setattr(module, "set_tournament_sync_status", AsyncMock())

    with pytest.raises(ValueError, match="integration account"):
        await ProviderSyncManager().sync_bracket("fixture", workspace_id="workspace-a")
    provider_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_tenant_import_requires_explicit_startgg_account(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from backend.api.routers import tournaments as router
    from backend.api.schemas import AddTournamentRequest

    monkeypatch.setattr(router, "get_tournament", AsyncMock(return_value=None))
    monkeypatch.setattr(router, "require_workspace_capacity", AsyncMock())
    with pytest.raises(HTTPException, match="Start.gg integration account"):
        await router.api_add_tournament(
            AddTournamentRequest(identifier="tournament/example"),
            SimpleNamespace(workspace_id="workspace-a"),
        )
