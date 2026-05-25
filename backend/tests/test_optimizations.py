import pytest
import os
import aiosqlite

from backend.core.database import (
    init_db,
    upsert_active_match,
    get_match_occupying_station,
    update_tournament_settings,
    upsert_tournament,
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
async def test_get_match_occupying_station(setup_test_db):
    # Case 1: Station is empty
    occupying = await get_match_occupying_station("station_1")
    assert occupying is None

    # Case 2: Station has an active match
    await upsert_active_match(
        set_id="set_1",
        station_id="station_1",
        status="in_progress",
        p1_name="P1",
        p2_name="P2"
    )
    occupying = await get_match_occupying_station("station_1")
    assert occupying is not None
    assert occupying["set_id"] == "set_1"

    # Case 3: Exclude current set_id
    occupying = await get_match_occupying_station("station_1", exclude_set_id="set_1")
    assert occupying is None

    # Case 4: Complete match does not occupy station
    await upsert_active_match(
        set_id="set_1",
        status="complete"
    )
    occupying = await get_match_occupying_station("station_1")
    assert occupying is None

@pytest.mark.asyncio
async def test_update_tournament_settings_batching(setup_test_db):
    # Seed tournament
    await upsert_tournament(
        slug="test-tourney",
        name="Test Tourney",
        event_name="Singles",
        event_id="12345",
        game="Street Fighter 6",
        raw_data="{}"
    )

    # Seed active matches
    await upsert_active_match(
        set_id="set_a",
        tournament_slug="test-tourney",
        status="not_started",
        round_name="Pools Match 1",
        phase_group="Pool A1"
    )
    await upsert_active_match(
        set_id="set_b",
        tournament_slug="test-tourney",
        status="not_started",
        round_name="Pools Match 2",
        phase_group="Pool A1"
    )

    # Update settings
    await update_tournament_settings(slug="test-tourney", bot_manage_limit="top8")
    
    # Check that they were correctly updated
    async with aiosqlite.connect(TEST_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT set_id, bot_enabled FROM active_matches") as cursor:
            rows = await cursor.fetchall()
            assert len(rows) == 2
            for row in rows:
                assert row["bot_enabled"] == 1
