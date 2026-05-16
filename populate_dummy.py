import asyncio
import os
import sys

# Add the backend directory to sys.path so we can import core.database
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT)

from backend.core.database import init_db, upsert_active_match, create_station, add_station_overlay, get_active_matches, get_stations

async def main():
    await init_db()
    
    stations = await get_stations()
    station_ids = [s["id"] for s in stations]
    
    if "station_1" not in station_ids:
        await create_station("station_1", "Stream A (Main Stage)")
        await add_station_overlay("station_1", "default")
    if "station_2" not in station_ids:
        await create_station("station_2", "Stream B (Side Stream)")
    
    matches = await get_active_matches(None)
    match_ids = [m["set_id"] for m in matches]
    
    if "dummy_live_1" not in match_ids:
        await upsert_active_match("dummy_live_1", tournament_slug="demo", p1_name="Daigo", p2_name="Justin Wong", p1_score=2, p2_score=1, p1_team="BST", p2_team="EG", round_name="Grand Finals", status="in_progress", station_id="station_1", match_number="GF-1", bot_enabled=True, swapped=False)
    if "dummy_called_1" not in match_ids:
        await upsert_active_match("dummy_called_1", tournament_slug="demo", p1_name="Tokido", p2_name="Punk", p1_score=0, p2_score=0, p1_team="Rohto", p2_team="FlyQuest", round_name="Losers Finals", status="called", station_id=None, match_number="LF-1", bot_enabled=False, swapped=False)
    if "dummy_complete_1" not in match_ids:
        await upsert_active_match("dummy_complete_1", tournament_slug="demo", p1_name="MenaRD", p2_name="Caba", p1_score=3, p2_score=0, p1_team="Bandits", p2_team="Bandits", round_name="Winners Semis", status="complete", station_id="station_2", match_number="WS-1", bot_enabled=True, swapped=False)
    
    print("Successfully populated dummy data into database.")

if __name__ == "__main__":
    asyncio.run(main())
