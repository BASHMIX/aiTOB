"""Flagged Start.gg V2 read gateway keeps legacy data and effects unchanged."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.core.contracts import (
    ITournamentProviderV2,
    ProviderCapabilitiesV2,
    ProviderSet,
    ProviderSetState,
    ProviderSnapshotRequestV2,
    ProviderSnapshotV2,
)
from backend.core.provider_feature_flags import ProviderFeatureFlags
from backend.core.provider_sync_manager import ProviderSyncManager


class _StartGGV2ReadFixture(ITournamentProviderV2):
    @property
    def provider_type(self) -> str:
        return "startgg"

    @property
    def capabilities_v2(self) -> ProviderCapabilitiesV2:
        return ProviderCapabilitiesV2()

    async def fetch_snapshot_v2(self, request: ProviderSnapshotRequestV2) -> ProviderSnapshotV2:
        return ProviderSnapshotV2(
            request=request,
            payload={"sets": [ProviderSet(id="set-1", state=ProviderSetState.CALLED)]},
        )

    async def execute_remote_command_v2(self, command):
        raise AssertionError("Phase 3 read gateway must not execute a command")


@pytest.mark.asyncio
async def test_disabled_flags_keep_the_legacy_fetch_sets_path(monkeypatch):
    from backend.core import provider_sync_manager as module

    legacy_provider = AsyncMock()
    legacy_provider.fetch_sets.return_value = [ProviderSet(id="set-1", state=ProviderSetState.CALLED)]
    monkeypatch.setattr(module, "get_tournament", AsyncMock(return_value={"slug": "fixture", "provider_type": "startgg"}))
    monkeypatch.setattr(module, "get_provider_for_tournament", AsyncMock(return_value=legacy_provider))
    monkeypatch.setattr(module, "sync_active_matches", AsyncMock())
    monkeypatch.setattr(module, "save_bracket_snapshot", AsyncMock())
    monkeypatch.setattr(module, "set_tournament_sync_status", AsyncMock())
    monkeypatch.setattr(module, "get_provider_feature_flags", lambda: ProviderFeatureFlags())
    manager = ProviderSyncManager()

    await manager.sync_bracket("fixture")

    legacy_provider.fetch_sets.assert_awaited_once_with("fixture", ignore_activity_guard=False)
    assert manager._v2_coordinator is None


@pytest.mark.asyncio
async def test_enabled_flags_use_only_the_v2_read_snapshot_and_keep_same_local_write_shape(monkeypatch):
    from backend.core import provider_sync_manager as module

    provider = _StartGGV2ReadFixture()
    sync_active_matches = AsyncMock()
    save_snapshot = AsyncMock()
    monkeypatch.setattr(module, "get_tournament", AsyncMock(return_value={"slug": "fixture", "provider_type": "startgg", "provider_account_id": "sgg-account"}))
    monkeypatch.setattr(module, "get_provider_for_tournament", AsyncMock(return_value=provider))
    monkeypatch.setattr(module, "set_tournament_sync_status", AsyncMock())
    monkeypatch.setattr(module, "sync_active_matches", sync_active_matches)
    monkeypatch.setattr(module, "save_bracket_snapshot", save_snapshot)
    monkeypatch.setattr(module, "set_tournament_sync_status", AsyncMock())
    monkeypatch.setattr(
        module, "get_provider_feature_flags",
        lambda: ProviderFeatureFlags(provider_v2_contracts_enabled=True, provider_coordinator_enabled=True),
    )
    manager = ProviderSyncManager()

    result = await manager.sync_bracket("fixture")

    assert result == {
        "sets": [{"id": "set-1", "state": int(ProviderSetState.CALLED), "round": "", "fullRoundText": "", "identifier": None, "event_id": "", "event_name": "", "phaseGroup": {"displayIdentifier": ""}, "p1": "TBD", "p2": "TBD", "p1_avatar": None, "p2_avatar": None, "p1_eid": None, "p2_eid": None}],
        "reason": "manual",
    }
    sync_active_matches.assert_awaited_once()
    save_snapshot.assert_awaited_once_with("fixture", result["sets"])
    assert manager._v2_coordinator is not None


@pytest.mark.asyncio
async def test_enabled_v2_reads_use_the_tournament_account_not_a_shared_default(monkeypatch):
    from backend.core import provider_sync_manager as module

    received_requests = []

    class CapturingProvider(_StartGGV2ReadFixture):
        async def fetch_snapshot_v2(self, request: ProviderSnapshotRequestV2) -> ProviderSnapshotV2:
            received_requests.append(request)
            return await super().fetch_snapshot_v2(request)

    monkeypatch.setattr(
        module,
        "get_tournament",
        AsyncMock(return_value={"slug": "fixture", "provider_type": "startgg", "provider_account_id": "account-a"}),
    )
    monkeypatch.setattr(module, "get_provider_for_tournament", AsyncMock(return_value=CapturingProvider()))
    monkeypatch.setattr(module, "sync_active_matches", AsyncMock())
    monkeypatch.setattr(module, "save_bracket_snapshot", AsyncMock())
    monkeypatch.setattr(module, "set_tournament_sync_status", AsyncMock())
    monkeypatch.setattr(
        module,
        "get_provider_feature_flags",
        lambda: ProviderFeatureFlags(provider_v2_contracts_enabled=True, provider_coordinator_enabled=True),
    )

    await ProviderSyncManager().sync_bracket("fixture")

    assert [request.provider_account_id for request in received_requests] == ["account-a"]


@pytest.mark.asyncio
async def test_enabled_flags_use_v2_reads_in_a_test_database_without_a_remote_mutation(tmp_path, monkeypatch):
    from backend.core import database
    from backend.core import provider_sync_manager as module

    db_path = tmp_path / "startgg-v2.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    await database.init_db()
    await database.upsert_tournament(
        "fixture", "Fixture", None, None, None, "{}", provider_type="startgg", provider_account_id="sgg-account"
    )
    provider = _StartGGV2ReadFixture()
    monkeypatch.setattr(module, "get_provider_for_tournament", AsyncMock(return_value=provider))
    monkeypatch.setattr(
        module, "get_provider_feature_flags",
        lambda: ProviderFeatureFlags(provider_v2_contracts_enabled=True, provider_coordinator_enabled=True),
    )

    await ProviderSyncManager().sync_bracket("fixture")
    snapshot = await database.get_bracket_snapshot("fixture")

    assert snapshot["sets"][0]["id"] == "set-1"


@pytest.mark.asyncio
async def test_enabled_v2_reads_fail_closed_for_unbound_tournament_before_provider_resolution(monkeypatch):
    from backend.core import provider_sync_manager as module

    provider_lookup = AsyncMock(side_effect=AssertionError("provider must not be resolved"))
    monkeypatch.setattr(
        module, "get_tournament",
        AsyncMock(return_value={"slug": "owned", "provider_type": "startgg", "workspace_id": "ws-a"}),
    )
    monkeypatch.setattr(module, "get_provider_for_tournament", provider_lookup)
    monkeypatch.setattr(module, "set_tournament_sync_status", AsyncMock())
    monkeypatch.setattr(
        module, "get_provider_feature_flags",
        lambda: ProviderFeatureFlags(provider_v2_contracts_enabled=True, provider_coordinator_enabled=True),
    )

    with pytest.raises(ValueError, match="tournament-bound integration account"):
        await ProviderSyncManager().sync_bracket("owned", workspace_id="ws-a")
    provider_lookup.assert_not_awaited()
