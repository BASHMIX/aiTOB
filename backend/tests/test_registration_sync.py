import pytest

from backend.core import database
from backend.core.registration_sync import sync_provider_roster
from backend.core.storage import dbapi as aiosqlite


@pytest.fixture
async def registration_db(tmp_path, monkeypatch):
    db_path = tmp_path / "registration.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    await database.init_db()
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES ('w1', 'w1', 'Workspace')")
        await db.execute("INSERT INTO tournaments (slug, name, workspace_id, provider_type, provider_account_id, provider_tournament_id) VALUES ('t1', 'Tournament', 'w1', 'startgg', 'a1', 'remote-t1')")
        await db.commit()
    return database.DB_PATH


@pytest.mark.asyncio
async def test_roster_sync_is_exact_scope_idempotent_and_marks_removals_for_review(registration_db):
    first = await sync_provider_roster(
        "t1", "w1", provider_type="startgg", provider_account_id="a1", external_scope_id="event-1",
        entrants=[{"id": "e1", "prefix": "FOX", "gamertag": "Alpha"}, {"id": "e2", "gamertag": "Bravo"}],
        provider_revision="r1",
    )
    assert first.added == 2
    second = await sync_provider_roster(
        "t1", "w1", provider_type="startgg", provider_account_id="a1", external_scope_id="event-1",
        entrants=[{"id": "e1", "prefix": "FOX", "gamertag": "Alpha"}, {"id": "e2", "gamertag": "Bravo"}],
        provider_revision="r1",
    )
    assert second.added == 0 and second.unchanged == 2
    third = await sync_provider_roster(
        "t1", "w1", provider_type="startgg", provider_account_id="a1", external_scope_id="event-1",
        entrants=[{"id": "e1", "prefix": "FOX", "gamertag": "Alpha Prime"}],
        provider_revision="r2",
    )
    assert third.updated == 1 and third.removed == 1
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute("SELECT provider_entrant_id, state, state_reason_code, prefix, gamertag FROM tournament_player_enrollments ORDER BY provider_entrant_id")).fetchall()
    assert rows[0]["state_reason_code"] == "provider_identity_changed"
    assert rows[0]["gamertag"] == "Alpha Prime"
    assert rows[1]["state_reason_code"] == "provider_entrant_removed"


@pytest.mark.asyncio
async def test_collision_moves_both_entries_to_review(registration_db):
    result = await sync_provider_roster(
        "t1", "w1", provider_type="challonge", provider_account_id="a1", external_scope_id="bracket-1",
        entrants=[{"id": "e1", "gamertag": "Alpha"}, {"id": "e2", "gamertag": "alpha"}],
    )
    assert result.collision_count == 1
    async with aiosqlite.connect(database.DB_PATH) as db:
        rows = await (await db.execute("SELECT state FROM tournament_player_enrollments ORDER BY provider_entrant_id")).fetchall()
    assert [row[0] for row in rows] == ["needs_review", "needs_review"]
