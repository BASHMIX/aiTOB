import asyncio
import sys
import os

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.startgg_client import StartGGClient

async def main():
    client = StartGGClient()
    info = await client.fetch_tournament_info("tournament/let-s-play-12") # use a real or random slug, wait I need a valid one or just let it fail gracefully
    print(info)

asyncio.run(main())
