import asyncio
import sqlite3
import httpx
import json

STARTGG_API_URL = "https://api.start.gg/gql/alpha"

TOURNAMENT_INFO_QUERY = """
query TournamentInfo($slug: String!) {
  tournament(slug: $slug) {
    id
    name
    events {
      id
      name
      videogame {
        name
      }
      entrants(query: {page: 1, perPage: 250}) {
        nodes {
          id
          name
        }
      }
    }
  }
}
"""

TOURNAMENT_SETS_QUERY = """
query TournamentSets($slug: String!) {
  tournament(slug: $slug) {
    events {
      sets(page: 1, perPage: 500) {
        nodes {
          id
          state
          fullRoundText
        }
      }
    }
  }
}
"""

async def test_schemas():
    conn = sqlite3.connect("backend/core/database.sqlite")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM connections WHERE key='STARTGG_API_TOKEN'")
    row = cursor.fetchone()
    token = row['value'] if row else None
    conn.close()
    
    if not token:
        print("No token found")
        return
        
    async with httpx.AsyncClient() as client:
        print("--- Testing Tournament Info (query: {page, perPage}) ---")
        resp1 = await client.post(
            STARTGG_API_URL, 
            json={"query": TOURNAMENT_INFO_QUERY, "variables": {"slug": "tournament/fnc1ststartgg"}},
            headers={"Authorization": f"Bearer {token}"}
        )
        print("Info status:", resp1.status_code)
        print("Info errors:", resp1.json().get("errors"))
        
        print("\n--- Testing Tournament Sets (page, perPage) ---")
        resp2 = await client.post(
            STARTGG_API_URL, 
            json={"query": TOURNAMENT_SETS_QUERY, "variables": {"slug": "tournament/fnc1ststartgg"}},
            headers={"Authorization": f"Bearer {token}"}
        )
        print("Sets status:", resp2.status_code)
        print("Sets errors:", resp2.json().get("errors"))

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(test_schemas())
