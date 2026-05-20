import os
import asyncio
import httpx
from dotenv import load_dotenv
import json

load_dotenv(override=True)

STARTGG_API_URL = "https://api.start.gg/gql/alpha"
STARTGG_API_TOKEN = os.getenv("STARTGG_API_TOKEN", "")

TOURNAMENT_QUERY = """query($slug:String!){tournament(slug:$slug){id name events{id name videogame{name}entrants(query:{perPage:100}){nodes{id name}}}}}"""
SETS_QUERY = """query($eventId:ID!){event(id:$eventId){sets(perPage:50){nodes{id fullRoundText state slots{entrant{id name}}}}}}"""

async def run_test():
    async with httpx.AsyncClient() as client:
        # Get Event ID
        resp1 = await client.post(STARTGG_API_URL, json={"query": TOURNAMENT_QUERY, "variables": {"slug": "tournament/fnc1ststartgg"}},
                                 headers={"Authorization": f"Bearer {STARTGG_API_TOKEN}"}, timeout=15)
        
        data = resp1.json()
        print("Tournament Data:")
        print(json.dumps(data, indent=2))
        
        tournament = data.get("data", {}).get("tournament")
        if not tournament:
            print("No tournament found!")
            return
            
        events = tournament.get("events", [])
        if not events:
            print("No events found!")
            return
            
        event_id = events[0]["id"]
        print(f"\nFetching sets for Event ID: {event_id}")
        
        # Get Sets
        resp2 = await client.post(STARTGG_API_URL, json={"query": SETS_QUERY, "variables": {"eventId": event_id}},
                                 headers={"Authorization": f"Bearer {STARTGG_API_TOKEN}"}, timeout=15)
        
        sets_data = resp2.json()
        print("\nSets Data:")
        print(json.dumps(sets_data, indent=2))
if __name__ == "__main__":
    asyncio.run(run_test())
