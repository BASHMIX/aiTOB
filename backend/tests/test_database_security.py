import pytest
import asyncio
from backend.core.database import (
    init_db,
    create_or_update_player,
    get_player,
    upsert_tournament,
    update_tournament_settings,
    get_tournament,
    create_station,
    update_station,
    get_stations,
    upsert_active_match,
    update_active_match,
    get_active_match,
    DB_PATH
)

@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()

@pytest.mark.asyncio
async def test_create_or_update_player_security():
    # Valid columns: 'gamer_tag', invalid: 'malicious" = 1 --'
    discord_id = "test_player_sec"
    await create_or_update_player(
        discord_id,
        gamer_tag="ValidTag",
        **{'malicious" = 1 --': "attack"}
    )
    player = await get_player(discord_id)
    assert player is not None
    assert player["gamer_tag"] == "ValidTag"
    assert "malicious\" = 1 --" not in player

    # Update path
    await create_or_update_player(
        discord_id,
        gamer_tag="UpdatedTag",
        **{'malicious" = 1 --': "attack2"}
    )
    player = await get_player(discord_id)
    assert player["gamer_tag"] == "UpdatedTag"

@pytest.mark.asyncio
async def test_update_tournament_settings_security():
    slug = "test_tourney_sec"
    await upsert_tournament(slug, "Test Tourney", "Event 1", "e1", "Game", "{}")

    # Update with malicious key
    await update_tournament_settings(
        slug,
        name="Secure Name",
        **{'malicious" = 1 --': "attack"}
    )

    t = await get_tournament(slug)
    assert t["name"] == "Secure Name"

@pytest.mark.asyncio
async def test_update_station_security():
    station_id = "test_station_sec"
    await create_station(station_id, "Sec Station")

    await update_station(
        station_id,
        name="Updated Sec Station",
        **{'malicious" = 1 --': "attack"}
    )

    stations = await get_stations()
    station = next((s for s in stations if s["id"] == station_id), None)
    assert station is not None
    assert station["name"] == "Updated Sec Station"

@pytest.mark.asyncio
async def test_update_active_match_security():
    set_id = "test_match_sec"
    await upsert_active_match(set_id, p1_name="P1")

    # Test update_active_match
    await update_active_match(
        set_id,
        p2_name="P2_Sec",
        **{'malicious" = 1 --': "attack"}
    )

    m = await get_active_match(set_id)
    assert m is not None
    assert m["p2_name"] == "P2_Sec"

    # Test upsert_active_match (update path)
    await upsert_active_match(
        set_id,
        p1_name="P1_Sec",
        **{'malicious2" = 1 --': "attack2"}
    )

    m2 = await get_active_match(set_id)
    assert m2["p1_name"] == "P1_Sec"
