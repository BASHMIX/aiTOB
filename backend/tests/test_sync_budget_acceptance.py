"""Phase-10 API-budget acceptance checks: cached UI reads make no provider calls."""
from __future__ import annotations

import json
import asyncio

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
