import asyncio
import os
import sys

# Add the backend directory to sys.path so we can import core.database
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT)

from backend.core.database import init_db, delete_active_match, delete_station

async def main():
    await init_db()
    
    # Delete dummy matches
    await delete_active_match("dummy_live_1")
    await delete_active_match("dummy_called_1")
    await delete_active_match("dummy_complete_1")
    
    # Delete dummy stations
    await delete_station("station_1")
    await delete_station("station_2")
    
    print("Dummy data removed.")

if __name__ == "__main__":
    asyncio.run(main())
