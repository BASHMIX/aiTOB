from __future__ import annotations

import asyncio
import json

from backend.core.storage import dbapi as aiosqlite
import pytest

from backend.core import database
from backend.core.provider_sync_manager import ProviderSyncManager
from backend.core.providers.challonge.provider import ChallongeProvider


class _Client:
    def __init__(self):
        self.participant_calls = self.match_calls = self.mutation_calls = 0

    async def participants(self, *_args):
        self.participant_calls += 1
        return [{"id": "p1", "attributes": {"name": "Alpha"}}, {"id": "p2", "attributes": {"name": "Bravo"}}]

    async def matches(self, *_args):
        self.match_calls += 1
        return [{"id": "m1", "attributes": {"state": "open", "player1_id": "p1", "player2_id": "p2", "revision": "1"}}]


@pytest.fixture
async def sync_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "sync.sqlite"))
    await database.init_db()
    await database.upsert_tournament(
        "challonge:account:fnc-jo:1", "FNC", None, None, None, json.dumps({}),
        provider_type="challonge", provider_tournament_id="1", provider_subdomain="fnc-jo", provider_account_id="account",
    )
    return "challonge:account:fnc-jo:1"


@pytest.mark.asyncio
async def test_sync_now_uses_one_read_only_full_snapshot_and_publishes_sqlite(sync_db, monkeypatch):
    from backend.core import provider_sync_manager as sync_module
    client = _Client()
    provider = ChallongeProvider(client)
    manager = ProviderSyncManager()
    monkeypatch.setattr(sync_module, "get_provider_for_tournament", lambda _slug: _resolved(provider))
    monkeypatch.setenv("CHALLONGE_READ_ENABLED", "true")

    result = await manager.sync_bracket(sync_db, reason="manual")

    assert client.participant_calls == client.match_calls == 1
    assert result["reason"] == "manual" and len(result["sets"]) == 1
    snapshot = await database.get_bracket_snapshot(sync_db)
    assert snapshot["sets"][0]["p1"] == "Alpha"


@pytest.mark.asyncio
async def test_stale_open_schedules_one_background_refresh_not_a_poller(sync_db, monkeypatch):
    manager = ProviderSyncManager()
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def sync_once(_slug, *, reason):
        nonlocal calls
        calls += 1
        assert reason == "stale-on-open"
        started.set()
        await release.wait()
        return {}

    monkeypatch.setattr(manager, "sync_bracket", sync_once)
    monkeypatch.setenv("CHALLONGE_READ_ENABLED", "true")

    assert await manager.maybe_sync_on_stale_open(sync_db) is True
    await started.wait()
    assert await manager.maybe_sync_on_stale_open(sync_db) is True
    assert calls == 1
    release.set()
    await asyncio.sleep(0)
    assert not manager._stale_open_tasks


@pytest.mark.asyncio
async def test_stale_open_can_be_disabled_for_fully_manual_economy(sync_db, monkeypatch):
    await database.update_tournament_settings(sync_db, economy_sync_on_stale_open=False)
    manager = ProviderSyncManager()
    monkeypatch.setenv("CHALLONGE_READ_ENABLED", "true")
    assert await manager.maybe_sync_on_stale_open(sync_db) is False
    assert not manager._stale_open_tasks


@pytest.mark.asyncio
async def test_failed_second_collection_page_never_replaces_last_healthy_bracket(sync_db, monkeypatch):
    from backend.core import provider_sync_manager as sync_module
    from backend.core.providers.challonge.client import ChallongeError

    class BrokenClient(_Client):
        async def matches(self, *_args):
            self.match_calls += 1
            raise ChallongeError("Challonge rejected the request.")

    manager = ProviderSyncManager()
    provider = ChallongeProvider(BrokenClient())
    monkeypatch.setattr(sync_module, "get_provider_for_tournament", lambda _slug: _resolved(provider))
    monkeypatch.setenv("CHALLONGE_READ_ENABLED", "true")

    with pytest.raises(ChallongeError):
        await manager.sync_bracket(sync_db)

    assert await database.get_bracket_snapshot(sync_db) == {"sets": [], "synced_at": None}
    async with aiosqlite.connect(database.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM active_matches") as cursor:
            assert (await cursor.fetchone())[0] == 0


async def _resolved(value):
    return value
