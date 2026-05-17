import asyncio
import aiohttp
import json

async def main():
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/active-matches") as resp:
            print(await resp.text())

if __name__ == "__main__":
    asyncio.run(main())
