"""Safety contract for removing a tournament from the Hub."""
from __future__ import annotations

import json

import pytest

from backend.core import database
from backend.core.storage import dbapi as aiosqlite


@pytest.fixture
async def removal_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "removal.sqlite"))
    await database.init_db()
    await database.upsert_tournament("t-remove", "Disposable", None, None, None, json.dumps({}))
    await database.upsert_tournament("t-keep", "Keep", None, None, None, json.dumps({}))
    return "t-remove"


@pytest.mark.asyncio
async def test_removal_is_blocked_while_a_tournament_owns_an_active_match(removal_db):
    await database.upsert_active_match("remove-live", tournament_slug=removal_db, status="in_progress", station_id="station-1")

    with pytest.raises(database.TournamentRemovalBlocked, match="active match"):
        await database.delete_tournament(removal_db)

    assert await database.get_tournament(removal_db)
    assert await database.get_active_match("remove-live")


@pytest.mark.asyncio
async def test_safe_removal_cleans_local_tournament_projection_and_releases_its_stale_station(removal_db):
    await database.upsert_active_match("remove-done", tournament_slug=removal_db, status="complete", station_id="station-1")
    await database.upsert_active_match("keep-done", tournament_slug="t-keep", status="complete", station_id="station-2")
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO stations (id, name, active_match_id) VALUES ('station-1', 'Station 1', 'remove-done')")
        await db.execute("INSERT INTO stations (id, name, active_match_id) VALUES ('station-2', 'Station 2', 'keep-done')")
        await db.execute("INSERT INTO planned_streams (set_id, tournament_slug) VALUES ('remove-done', ?)", (removal_db,))
        await db.execute("INSERT INTO provider_bracket_snapshots (tournament_slug, sets_json) VALUES (?, '[]')", (removal_db,))
        await db.execute("INSERT INTO provider_reconciliation_audit (tournament_slug, provider_type, action, reason) VALUES (?, 'startgg', 'test', 'test')", (removal_db,))
        await db.commit()

    await database.delete_tournament(removal_db)

    assert await database.get_tournament(removal_db) is None
    assert await database.get_active_match("remove-done") is None
    assert await database.get_active_match("keep-done")
    async with aiosqlite.connect(database.DB_PATH) as db:
        assert (await (await db.execute("SELECT active_match_id FROM stations WHERE id='station-1'")).fetchone())[0] is None
        assert (await (await db.execute("SELECT active_match_id FROM stations WHERE id='station-2'")).fetchone())[0] == "keep-done"
        assert (await (await db.execute("SELECT COUNT(*) FROM planned_streams WHERE tournament_slug=?", (removal_db,))).fetchone())[0] == 0
        assert (await (await db.execute("SELECT COUNT(*) FROM provider_bracket_snapshots WHERE tournament_slug=?", (removal_db,))).fetchone())[0] == 0


@pytest.mark.asyncio
async def test_reset_active_matches_is_workspace_scoped_for_colliding_slugs(tmp_path, monkeypatch):
    """Resetting one tenant's Hub projection cannot wipe a sibling tenant."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "reset-scope.sqlite"))
    await database.init_db()
    await database.upsert_active_match("tenant-a-set", tournament_slug="same-slug", workspace_id="ws-a", status="not_started")
    await database.upsert_active_match("tenant-b-set", tournament_slug="same-slug", workspace_id="ws-b", status="not_started")

    await database.delete_tournament_active_matches("same-slug", "ws-a")

    assert await database.get_active_match("tenant-a-set", workspace_id="ws-a") is None
    assert await database.get_active_match("tenant-b-set", workspace_id="ws-b")
