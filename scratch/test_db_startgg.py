import asyncio
import sqlite3
import httpx
import json
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

STARTGG_API_URL = "https://api.start.gg/gql/alpha"
TOURNAMENT_QUERY = """query($slug:String!){tournament(slug:$slug){id name events{id name videogame{name}entrants(query:{perPage:100}){nodes{id name}}}}}"""

async def test_lookup_and_query():
    db_path = os.path.join(PROJECT_ROOT, "backend", "core", "database.sqlite")
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        print("Start the API at least once (`python run.py`) so init_db() creates the schema.")
        return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Try fetching from connections first, then global_settings
    token = None
    try:
        cursor.execute("SELECT value FROM connections WHERE key='STARTGG_API_TOKEN'")
        row = cursor.fetchone()
        if row:
            token = row['value']
    except Exception as e:
        print("Error fetching from connections:", e)
        
    if not token:
        try:
            cursor.execute("SELECT value FROM global_settings WHERE key='STARTGG_API_TOKEN'")
            row = cursor.fetchone()
            if row:
                token = row['value']
        except Exception as e:
            print("Error fetching from global_settings:", e)
            
    conn.close()
    
    if not token:
        print("STARTGG_API_TOKEN not found in database!")
        return
        
    print(f"Using Token from DB: {token[:4]}...{token[-4:] if len(token) > 8 else ''}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                STARTGG_API_URL, 
                json={"query": TOURNAMENT_QUERY, "variables": {"slug": "tournament/fnc1ststartgg"}},
                headers={"Authorization": f"Bearer {token}"}, 
                timeout=15
            )
            print("Status Code:", resp.status_code)
            data = resp.json()
            if "errors" in data:
                print("API returned errors:")
                print(json.dumps(data["errors"], indent=2))
            else:
                print("Success! Tournament data fetched:")
                print(json.dumps(data.get("data", {}).get("tournament", {}), indent=2))
        except Exception as e:
            print("Request failed:", e)

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(test_lookup_and_query())
