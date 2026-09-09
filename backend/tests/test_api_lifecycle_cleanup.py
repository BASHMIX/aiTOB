"""API startup/shutdown must own its tasks and never copy legacy secrets."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_api_shutdown_drains_started_tasks_and_does_not_import_secrets(monkeypatch):
    from backend.api import main
    from backend.core import provider_feature_flags
    from backend.core.providers.startgg import client
    from backend.core.provider_sync_manager import sync_manager
    started, cleaned = asyncio.Event(), asyncio.Event()
    async def reconciliation():
        started.set()
        try:
            await asyncio.Future()
        finally:
            await asyncio.sleep(0.01)
            cleaned.set()
    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(main, "sync_tracked_tournaments", AsyncMock())
    monkeypatch.setattr(main, "reconciliation_loop", reconciliation)
    monkeypatch.setattr(main, "get_all_settings", AsyncMock(return_value={}))
    store = AsyncMock()
    monkeypatch.setattr(main, "set_setting", store)
    monkeypatch.setattr(provider_feature_flags, "get_provider_feature_flags", lambda: SimpleNamespace(
        challonge_local_workflow_enabled=False, challonge_read_enabled=False,
    ))
    probe = AsyncMock(return_value={"status": "test"})
    monkeypatch.setattr(client, "get_client", lambda: SimpleNamespace(token=None, probe_token_permissions=probe))
    monkeypatch.setattr(sync_manager, "close_live_schedules", AsyncMock())
    monkeypatch.setenv("STARTGG_API_TOKEN", "fake-test-only")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-test-only")
    monkeypatch.setenv("HUB_PASSWORD", "fake-test-only")
    monkeypatch.delenv("STARTGG_TOKEN_PROBE_ON_STARTUP", raising=False)
    # Keep this worker-drain test independent from a cutover process-wide
    # pause switch that may be present in the invoking environment.
    monkeypatch.delenv("AITOB_DISABLE_BACKGROUND_WORKERS", raising=False)
    await main.startup_event()
    await started.wait()
    await main.shutdown_event()
    try:
        assert cleaned.is_set()
        # Provider probes are opt-in; startup itself must not contact Start.gg.
        assert probe.await_count == 0
        assert not {call.args[0] for call in store.call_args_list} & {"STARTGG_API_TOKEN", "GOOGLE_API_KEY", "HUB_PASSWORD"}
    finally:
        # On the pre-fix implementation, clean up only this test's leaked task.
        for task in asyncio.all_tasks():
            if task.get_coro().__name__ == "reconciliation":
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_api_startup_can_pause_background_workers_for_cutover(monkeypatch):
    from backend.api import main
    from backend.core import provider_feature_flags
    from backend.core.provider_sync_manager import sync_manager

    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(main, "sync_tracked_tournaments", AsyncMock())
    reconciliation = AsyncMock()
    monkeypatch.setattr(main, "reconciliation_loop", reconciliation)
    monkeypatch.setattr(provider_feature_flags, "get_provider_feature_flags", lambda: SimpleNamespace(
        challonge_local_workflow_enabled=True, challonge_read_enabled=True,
    ))
    restore = AsyncMock()
    monkeypatch.setattr("backend.core.recovery.RecoveryService.restore", restore)
    monkeypatch.setattr(sync_manager, "restore_live_schedules", AsyncMock())
    monkeypatch.setattr(sync_manager, "close_live_schedules", AsyncMock())
    monkeypatch.setenv("AITOB_DISABLE_BACKGROUND_WORKERS", "true")
    monkeypatch.delenv("STARTGG_TOKEN_PROBE_ON_STARTUP", raising=False)

    await main.startup_event()
    try:
        main.sync_tracked_tournaments.assert_not_awaited()
        reconciliation.assert_not_awaited()
        restore.assert_not_awaited()
        sync_manager.restore_live_schedules.assert_not_awaited()
    finally:
        await main.shutdown_event()
