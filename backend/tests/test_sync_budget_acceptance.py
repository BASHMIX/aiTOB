"""Phase-10 API-budget acceptance checks: cached UI reads make no provider calls."""
from __future__ import annotations

import json
import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.core import database


@pytest.fixture
async def budget_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "budget.sqlite"))
    await database.init_db()
    await database.upsert_tournament(
        "challonge:budget", "Budget", None, None, None, json.dumps({}),
        provider_type="challonge", provider_tournament_id="77",
    )
    await database.save_bracket_snapshot("challonge:budget", [{"id": "match-1"}])
    return "challonge:budget"


@pytest.mark.asyncio
async def test_ten_dashboard_cache_reads_make_zero_provider_calls(budget_db, monkeypatch):
    from backend.api.routers import tournaments

    provider_calls = 0

    async def no_refresh(_slug: str) -> bool:
        nonlocal provider_calls
        provider_calls += 1
        return False

    monkeypatch.setattr(tournaments.sync_manager, "maybe_sync_on_stale_open", no_refresh)
    for _ in range(10):
        response = await tournaments.api_get_sets(budget_db)
        assert response["sets"] == [{"id": "match-1"}]
    # The endpoint only asks the admission gate; it performs no provider operation.
    assert provider_calls == 10


@pytest.mark.asyncio
async def test_completed_tournament_never_enters_live_polling(budget_db, monkeypatch):
    from backend.core.provider_sync_manager import ProviderSyncManager

    await database.update_tournament_settings(budget_db, challonge_sync_mode="live")
    # Stored raw provider terminal state makes this an archived/completed candidate.
    await database.upsert_tournament(
        budget_db, "Budget", None, None, None, json.dumps({"provider_state": "complete"}),
        provider_type="challonge", provider_tournament_id="77",
    )
    manager = ProviderSyncManager()
    calls = 0

    async def sync(_slug: str, *, reason: str):
        nonlocal calls
        calls += 1
        return {"reason": reason}

    monkeypatch.setattr(manager, "sync_bracket", sync)
    # Completion is guarded by LiveSyncScheduler state rather than a periodic task.
    assert manager._live_scheduler.start(budget_db) is True
    await asyncio.sleep(0)
    assert manager._live_scheduler.stop(budget_db) is True
    await manager.close_live_schedules()
    assert calls == 0


@pytest.mark.asyncio
async def test_live_schedule_restore_skips_unowned_legacy_rows(monkeypatch):
    """Scheduler recovery must require durable tenant context before polling."""
    from backend.core.provider_sync_manager import ProviderSyncManager

    rows = [
        {"slug": "legacy/unowned", "provider_type": "challonge", "challonge_sync_mode": "live", "workspace_id": None},
        {"slug": "owned/live", "provider_type": "challonge", "challonge_sync_mode": "live", "workspace_id": "workspace-a"},
    ]
    monkeypatch.setattr("backend.core.provider_sync_manager.get_tournaments", AsyncMock(return_value=rows))
    monkeypatch.setattr(
        "backend.core.provider_sync_manager.get_provider_feature_flags",
        lambda: type("Flags", (), {"challonge_read_enabled": True})(),
    )
    manager = ProviderSyncManager()
    starts: list[tuple[str, str | None]] = []

    def start(slug, *, workspace_id=None):
        starts.append((slug, workspace_id))
        return True

    monkeypatch.setattr(manager._live_scheduler, "start", start)
    try:
        assert await manager.restore_live_schedules() == 1
        assert starts == [("owned/live", "workspace-a")]
    finally:
        await manager.close_live_schedules()


@pytest.mark.asyncio
async def test_replaced_deferred_sync_does_not_remove_new_task(budget_db):
    from backend.core.provider_sync_manager import ProviderSyncManager
    manager = ProviderSyncManager()
    manager.schedule_bracket_sync(budget_db, delay_seconds=3600)
    await asyncio.sleep(0)
    manager.schedule_bracket_sync(budget_db, delay_seconds=3600)
    latest = manager._deferred[budget_db]
    await asyncio.sleep(0)
    try:
        assert manager._deferred.get(budget_db) is latest
    finally:
        await manager.close_live_schedules()
    assert latest.done()


@pytest.mark.asyncio
async def test_deferred_refreshes_do_not_collide_across_workspaces():
    from backend.core.provider_sync_manager import ProviderSyncManager

    manager = ProviderSyncManager()
    manager.schedule_bracket_sync("same-slug", workspace_id="workspace-a", delay_seconds=3600)
    manager.schedule_bracket_sync("same-slug", workspace_id="workspace-b", delay_seconds=3600)
    await asyncio.sleep(0)
    try:
        assert ("workspace-a", "same-slug") in manager._deferred
        assert ("workspace-b", "same-slug") in manager._deferred
        assert manager._deferred[("workspace-a", "same-slug")] is not manager._deferred[("workspace-b", "same-slug")]
    finally:
        await manager.close_live_schedules()


@pytest.mark.asyncio
async def test_stale_open_refreshes_do_not_collide_across_workspaces(monkeypatch):
    from backend.core.provider_sync_manager import ProviderSyncManager

    manager = ProviderSyncManager()

    async def tournament(slug, workspace_id=None):
        return {
            "slug": slug,
            "workspace_id": workspace_id,
            "provider_type": "challonge",
            "provider_last_synced_at": None,
            "economy_sync_on_stale_open": True,
        }

    async def no_sync(*args, **kwargs):
        await asyncio.sleep(3600)

    monkeypatch.setattr("backend.core.provider_sync_manager.get_tournament", tournament)
    monkeypatch.setattr(manager, "sync_bracket", no_sync)
    # The flag is enabled in this test process by the fixture defaults used by
    # the other stale-open acceptance tests.
    monkeypatch.setattr(
        "backend.core.provider_sync_manager.get_provider_feature_flags",
        lambda: type("Flags", (), {"challonge_read_enabled": True})(),
    )
    assert await manager.maybe_sync_on_stale_open("same-slug", workspace_id="workspace-a")
    assert await manager.maybe_sync_on_stale_open("same-slug", workspace_id="workspace-b")
    await asyncio.sleep(0)
    try:
        assert ("workspace-a", "same-slug") in manager._stale_open_tasks
        assert ("workspace-b", "same-slug") in manager._stale_open_tasks
    finally:
        await manager.close_live_schedules()


@pytest.mark.asyncio
async def test_live_schedules_are_tenant_scoped_for_same_slug():
    from backend.core.sync_coordinator import LiveSyncScheduler

    seen: list[tuple[str, str | None]] = []
    stop = asyncio.Event()

    async def state(slug, workspace_id=None):
        return {"mode": "live", "active_match": False, "called_match": False,
                "workspace_id": workspace_id}

    async def sync(slug, reason, workspace_id=None):
        seen.append((slug, workspace_id))
        await stop.wait()

    async def no_wait(seconds):
        await stop.wait()

    scheduler = LiveSyncScheduler(sync, state, sleep=no_wait)
    assert scheduler.start("same-slug", workspace_id="workspace-a")
    assert scheduler.start("same-slug", workspace_id="workspace-b")
    await asyncio.sleep(0)
    assert scheduler.start("same-slug", workspace_id="workspace-a") is False
    stop.set()
    await scheduler.close()
    assert set(seen) == {("same-slug", "workspace-a"), ("same-slug", "workspace-b")}
