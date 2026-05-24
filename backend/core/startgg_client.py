import httpx
import asyncio
import os
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

STARTGG_API_TOKEN = os.getenv("STARTGG_API_TOKEN")
STARTGG_API_URL = "https://api.start.gg/gql/alpha"

_client_instance: Optional["StartGGClient"] = None

def get_client() -> "StartGGClient":
    global _client_instance
    if _client_instance is None:
        _client_instance = StartGGClient()
    return _client_instance

class StartGGClient:
    def __init__(self, token: str = STARTGG_API_TOKEN):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.last_request_time = 0
        self.request_count = 0
        self.rate_limit_lock = asyncio.Lock()

    async def _handle_rate_limit(self):
        async with self.rate_limit_lock:
            now = time.time()
            if now - self.last_request_time > 60:
                self.request_count = 0
                self.last_request_time = now
            
            if self.request_count >= 75:  # Safe margin below 80
                wait_time = 60 - (now - self.last_request_time)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self.request_count = 0
                self.last_request_time = time.time()
            
            self.request_count += 1

    async def query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        await self._handle_rate_limit()
        
        # Ensure we have a token (fetch from DB if needed)
        token = self.token
        if not token:
            from backend.core.database import get_setting, get_connection
            token = await get_setting("STARTGG_API_TOKEN") or await get_connection("STARTGG_API_TOKEN")
        
        if not token:
            raise Exception("Start.gg API Token not configured")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(
                    STARTGG_API_URL,
                    json={"query": query, "variables": variables or {}},
                    headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
                
                if "errors" in data:
                    print(f"[STARTGG] API Error: {data['errors']}")
                    # Surface the actual error message if possible
                    err_msg = data['errors'][0].get('message', 'Unknown Start.gg Error')
                    raise Exception(f"Start.gg API Error: {err_msg}")
                
                return data.get("data", {})
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Retry once after sleep if rate limited
                    await asyncio.sleep(30)
                    return await self.query(query, variables)
                print(f"[STARTGG] HTTP Error: {e.response.status_code} - {e.response.text}")
                raise Exception(f"Start.gg HTTP Error: {e.response.status_code}")
            except Exception as e:
                print(f"[STARTGG] Query failed: {e}")
                raise e

    async def fetch_tournament_info(self, slug: str) -> Optional[Dict[str, Any]]:
        """Fetch basic tournament info and entrants."""
        query = """
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
                  participants {
                    user {
                      images {
                        url
                        type
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        try:
            data = await self.query(query, {"slug": slug})
            return data.get("tournament")
        except Exception as e:
            print(f"Error fetching tournament info: {e}")
            return None

    async def fetch_tournament_sets(self, slug: str) -> List[Dict[str, Any]]:
        """Fetch all sets for a tournament event."""
        query = """
        query TournamentSets($slug: String!) {
          tournament(slug: $slug) {
            events {
              sets(page: 1, perPage: 500) {
                nodes {
                  id
                  state
                  fullRoundText
                  identifier
                  phaseGroup {
                    displayIdentifier
                  }
                  slots {
                    entrant {
                      id
                      name
                      participants {
                        user {
                          images {
                            url
                            type
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        data = await self.query(query, {"slug": slug})
        sets = []
        if data.get("tournament") and data["tournament"].get("events"):
            for event in data["tournament"]["events"]:
                if event.get("sets") and event["sets"].get("nodes"):
                    for s in event["sets"]["nodes"]:
                        # Helper to extract avatar
                        for i, slot in enumerate(s.get("slots", [])):
                            entrant = slot.get("entrant")
                            avatar = None
                            if entrant:
                                participants = entrant.get("participants", []) or []
                                for p in participants:
                                    user = p.get("user")
                                    if user:
                                        u_images = user.get("images", []) or []
                                        for img in u_images:
                                            if img.get("type") == "profile":
                                                avatar = img.get("url")
                                                break
                                        if not avatar and u_images:
                                            avatar = u_images[0].get("url")
                                        if avatar:
                                            break
                            s[f"p{i+1}_avatar"] = avatar
                            s[f"p{i+1}"] = entrant.get("name") if entrant else "TBD"
                            s[f"p{i+1}_eid"] = entrant.get("id") if entrant else None
                        
                        # Flatten complex objects for frontend/DB
                        s["round"] = s.get("fullRoundText", "")
                        pg = s.get("phaseGroup")
                        s["phaseGroup"] = pg.get("displayIdentifier", "") if isinstance(pg, dict) else (pg or "")
                        # Remove potentially circular or too-large objects
                        if "slots" in s: del s["slots"]
                        
                        sets.append(s)
        return sets

    async def report_set_score(self, set_id: str, winner_id: str, scores: List[Dict[str, Any]]) -> bool:
        """Report match result (winner, scores) via gameData array."""
        mutation = """
        mutation ReportBracketSet($setId: ID!, $winnerId: ID!, $gameData: [BracketSetGameDataInput]) {
          reportBracketSet(setId: $setId, winnerId: $winnerId, gameData: $gameData) {
            id
            state
          }
        }
        """
        try:
            await self.query(mutation, {
                "setId": set_id,
                "winnerId": winner_id,
                "gameData": scores
            })
            return True
        except Exception as e:
            print(f"Failed to report score: {e}")
            return False

    def _generate_game_data(self, winner_id: str, entrant1_id: str, entrant2_id: str,
                             entrant1_score: int, entrant2_score: int) -> list:
        """Convert set-level scores to per-game gameData entries.

        For a 2-0 result (entrant1 wins), produces:
          [{winnerId:e1_id, entrant1Score:1, entrant2Score:0, gameNum:1},
           {winnerId:e1_id, entrant1Score:1, entrant2Score:0, gameNum:2}]
        """
        game_data = []
        game_num = 1
        for _ in range(entrant1_score):
            game_data.append({
                "winnerId": entrant1_id,
                "entrant1Score": 1,
                "entrant2Score": 0,
                "gameNum": game_num
            })
            game_num += 1
        for _ in range(entrant2_score):
            game_data.append({
                "winnerId": entrant2_id,
                "entrant1Score": 0,
                "entrant2Score": 1,
                "gameNum": game_num
            })
            game_num += 1
        return game_data

    async def report_set_score_normal(self, set_id: str, winner_id: str,
                                       p1_id: str, p2_id: str,
                                       p1_score: int, p2_score: int) -> dict:
        """Report a set with per-game gameData.

        Marks set as in_progress on Start.gg if needed (non-fatal),
        fetches entrant slot order internally, maps scores to correct slot,
        then sends one gameData entry per game won.
        Returns the API response.
        """
        # Ensure set is in_progress on Start.gg before reporting
        try:
            await self.mark_in_progress(set_id)
        except Exception:
            pass  # Non-critical; the report mutation will validate state

        # Fetch entrant order to map our p1/p2 to Start.gg slot order
        entrant1_id = p1_id
        entrant2_id = p2_id
        entrant1_score = p1_score
        entrant2_score = p2_score
        try:
            entrant_ids = await self.fetch_set_entrant_order(set_id)
            if len(entrant_ids) >= 2 and entrant_ids[0] == p2_id:
                entrant1_id = p2_id
                entrant2_id = p1_id
                entrant1_score = p2_score
                entrant2_score = p1_score
        except Exception:
            print(f"[STARTGG] Failed to fetch entrant order for {set_id}, using default ordering")

        game_data = self._generate_game_data(
            winner_id, entrant1_id, entrant2_id,
            entrant1_score, entrant2_score
        )

        mutation = """
        mutation ReportBracketSet($setId: ID!, $winnerId: ID!, $gameData: [BracketSetGameDataInput]) {
          reportBracketSet(setId: $setId, winnerId: $winnerId, gameData: $gameData) {
            id
            state
          }
        }
        """
        return await self.query(mutation, {
            "setId": set_id,
            "winnerId": winner_id,
            "gameData": game_data
        })

    async def report_set_winner_only(self, set_id: str, winner_id: str) -> dict:
        """Report a set with winner only (no scores)."""
        mutation = """
        mutation SimpleReport($setId: ID!, $winnerId: ID!) {
          reportBracketSet(setId: $setId, winnerId: $winnerId) { id state }
        }
        """
        return await self.query(mutation, {"setId": set_id, "winnerId": winner_id})

    async def fetch_set_entrant_order(self, set_id: str) -> list:
        """Fetch the slot/entrant ordering for a set from Start.gg."""
        q = """
        query SetEntrants($id: ID!) {
          set(id: $id) {
            slots { entrant { id } }
          }
        }
        """
        result = await self.query(q, {"id": set_id})
        slots = result.get("set", {}).get("slots", [])
        return [
            str(slot.get("entrant", {}).get("id"))
            for slot in slots
            if slot.get("entrant")
        ]

    async def fetch_set_state(self, set_id: str) -> int:
        """Fetch the numeric state of a set from Start.gg."""
        q = """
        query SetState($id: ID!) {
          set(id: $id) { state }
        }
        """
        result = await self.query(q, {"id": set_id})
        return result.get("set", {}).get("state")

    async def mark_set_dq(self, set_id: str, entrant_id: str) -> bool:
        """DQ a player and advance opponent using reportBracketSet."""
        mutation = """
        mutation MarkSetDQ($setId: ID!, $winnerId: ID!) {
          reportBracketSet(setId: $setId, winnerId: $winnerId) {
            id
            state
          }
        }
        """
        try:
            await self.query(mutation, {"setId": set_id, "winnerId": entrant_id})
            return True
        except Exception as e:
            print(f"Failed to mark DQ: {e}")
            return False

    async def reset_set(self, set_id: str) -> bool:
        """Reset/reopen a completed set."""
        mutation = """
        mutation ResetSet($setId: ID!) {
          resetSet(setId: $setId) {
            id
            state
          }
        }
        """
        try:
            await self.query(mutation, {"setId": set_id})
            return True
        except Exception as e:
            print(f"Failed to reset set: {e}")
            return False

    async def mark_in_progress(self, set_id: str) -> bool:
        """Mark a set as In Progress on Start.gg."""
        mutation = """
        mutation MarkInProgress($setId: ID!) {
          markSetInProgress(setId: $setId) {
            id
            state
          }
        }
        """
        try:
            await self.query(mutation, {"setId": set_id})
            return True
        except Exception as e:
            print(f"Failed to mark in progress: {e}")
            return False
