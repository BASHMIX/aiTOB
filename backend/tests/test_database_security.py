import pytest
import os
import aiosqlite

from backend.core.database import (
    init_db,
    update_station,
    create_or_update_player,
    update_tournament_settings,
    update_active_match,
    upsert_active_match,
    DB_PATH
)

TEST_DB_PATH = "backend/core/test_database.sqlite"

@pytest.fixture
async def setup_test_db():
    import backend.core.database
    import backend.core.match_state

    orig_db_path = backend.core.database.DB_PATH
    backend.core.database.DB_PATH = TEST_DB_PATH
    backend.core.match_state.DB_PATH = TEST_DB_PATH

    await init_db()

    yield

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    backend.core.database.DB_PATH = orig_db_path
    backend.core.match_state.DB_PATH = orig_db_path

@pytest.mark.asyncio
async def test_update_station_sql_injection(setup_test_db):
    import backend.core.database
    await backend.core.database.create_station("station_sec_1", "Security Station")

    # Try updating with malicious column
    try:
        await update_station("station_sec_1", name="Hacked Station", **{"name='Hacked Station'; DROP TABLE stations; --": "test"})
    except aiosqlite.OperationalError:
        pytest.fail("SQL injection triggered!")

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name FROM stations WHERE id = 'station_sec_1'") as cursor:
            row = await cursor.fetchone()
            assert row["name"] == "Hacked Station" # Legitimate param still works

        # Verify table still exists
        async with db.execute("SELECT count(*) FROM stations") as cursor:
            row = await cursor.fetchone()
            assert row[0] >= 1

@pytest.mark.asyncio
async def test_create_or_update_player_sql_injection(setup_test_db):
    try:
        await create_or_update_player("user_sec_1", gamer_tag="Hacked Player", **{"gamer_tag='Hack'; DROP TABLE players; --": "test"})
    except aiosqlite.OperationalError:
        pytest.fail("SQL injection triggered!")

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT gamer_tag FROM players WHERE discord_id = 'user_sec_1'") as cursor:
            row = await cursor.fetchone()
            assert row["gamer_tag"] == "Hacked Player"

        # Verify table still exists
        async with db.execute("SELECT count(*) FROM players") as cursor:
            row = await cursor.fetchone()
            assert row[0] >= 1

@pytest.mark.asyncio
async def test_update_tournament_settings_sql_injection(setup_test_db):
    import backend.core.database
    await backend.core.database.upsert_tournament("tourney_sec_1", "Tourney", "Event", "1", "Game", "{}")

    try:
        await update_tournament_settings("tourney_sec_1", name="Hacked Tourney", **{"name='Hack'; DROP TABLE tournaments; --": "test"})
    except aiosqlite.OperationalError:
        pytest.fail("SQL injection triggered!")

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name FROM tournaments WHERE slug = 'tourney_sec_1'") as cursor:
            row = await cursor.fetchone()
            assert row["name"] == "Hacked Tourney"

        # Verify table still exists
        async with db.execute("SELECT count(*) FROM tournaments") as cursor:
            row = await cursor.fetchone()
            assert row[0] >= 1

@pytest.mark.asyncio
async def test_update_active_match_sql_injection(setup_test_db):
    await upsert_active_match("match_sec_1", p1_name="P1")

    try:
        await update_active_match("match_sec_1", p1_name="Hacked P1", **{"p1_name='Hack'; DROP TABLE active_matches; --": "test"})
    except aiosqlite.OperationalError:
        pytest.fail("SQL injection triggered!")

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT p1_name FROM active_matches WHERE set_id = 'match_sec_1'") as cursor:
            row = await cursor.fetchone()
            assert row["p1_name"] == "Hacked P1"

        # Verify table still exists
        async with db.execute("SELECT count(*) FROM active_matches") as cursor:
            row = await cursor.fetchone()
            assert row[0] >= 1
