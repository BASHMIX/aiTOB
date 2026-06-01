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
    MAX_RETRIES = 3

    def __init__(self, token: str = STARTGG_API_TOKEN):
        self.token = token
        self._http_client: Optional[httpx.AsyncClient] = None
        self.last_request_time = 0
        self.request_count = 0
        self.rate_limit_lock = asyncio.Lock()

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=60.0,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

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
        last_exception = None
        for attempt in range(self.MAX_RETRIES + 1):
            await self._handle_rate_limit()
            
            # Ensure we have a token (fetch from DB if needed and cache it)
            if not self.token:
                from backend.core.database import get_setting, get_connection
                self.token = await get_setting("STARTGG_API_TOKEN") or await get_connection("STARTGG_API_TOKEN")
            
            if not self.token:
                raise Exception("Start.gg API Token not configured")

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            client = await self._get_http_client()
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
                if e.response.status_code == 429 and attempt < self.MAX_RETRIES:
                    wait = min(30 * (2 ** attempt), 120)
                    print(f"[STARTGG] Rate limited, retry {attempt+1}/{self.MAX_RETRIES} in {wait}s")
                    await asyncio.sleep(wait)
                    last_exception = e
                    continue
                print(f"[STARTGG] HTTP Error: {e.response.status_code} - {e.response.text}")
                raise Exception(f"Start.gg HTTP Error: {e.response.status_code}")
            except Exception as e:
                print(f"[STARTGG] Query failed: {e}")
                raise e

        raise Exception(f"Start.gg request failed after {self.MAX_RETRIES} retries: {last_exception}")

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

        Pre-flight checks reject preview sets and stale states.
        Marks set ACTIVE on Start.gg first; surfaces the real error if that fails
        (was silently swallowed before, masking the cause of report failures).
        """
        # 1. Preview sets cannot be mutated — fail fast with a useful message.
        if str(set_id).startswith("preview"):
            raise Exception(
                f"Set {set_id} is a preview/unresolved set on Start.gg and cannot be reported. "
                "Wait for upstream brackets to finalize."
            )

        # 2. Confirm the set is in a reportable state (READY=4, CALLED=6, ACTIVE=2).
        #    COMPLETED=3 or CREATED=1 cannot be reported.
        try:
            current_state = await self.fetch_set_state(set_id)
        except Exception:
            current_state = None
        if current_state == 3:
            raise Exception(f"Set {set_id} is already COMPLETED on Start.gg. Reset before re-reporting.")
        if current_state == 1:
            raise Exception(
                f"Set {set_id} is in CREATED state — upstream matches have not resolved. "
                "Cannot mark in progress yet."
            )

        # 3. Transition to ACTIVE. Surface failures (do not swallow) so the operator
        #    sees the actual root cause (permissions, state, missing entrants, etc.).
        if current_state != 2:  # already ACTIVE? skip
            ok = await self.mark_in_progress(set_id)
            if not ok:
                raise Exception(
                    f"markSetInProgress failed for set {set_id}. "
                    "Common causes: API token lacks tournament admin scope, "
                    "or upstream bracket has not advanced entrants into this set."
                )

        # 4. Map p1/p2 scores to start.gg's canonical slot order.
        entrant1_id, entrant2_id = p1_id, p2_id
        entrant1_score, entrant2_score = p1_score, p2_score
        try:
            entrant_ids = await self.fetch_set_entrant_order(set_id)
            if len(entrant_ids) >= 2 and entrant_ids[0] == p2_id:
                entrant1_id, entrant2_id = p2_id, p1_id
                entrant1_score, entrant2_score = p2_score, p1_score
        except Exception:
            print(f"[STARTGG] Failed to fetch entrant order for {set_id}, using default ordering")

        game_data = self._generate_game_data(
            winner_id, entrant1_id, entrant2_id,
            entrant1_score, entrant2_score
        )

        from backend.core.providers.startgg.queries import REPORT_BRACKET_SET
        return await self.query(REPORT_BRACKET_SET, {
            "setId": set_id,
            "winnerId": winner_id,
            "gameData": game_data,
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

    async def mark_set_dq(self, set_id: str, winner_id: str) -> bool:
        """Disqualify the loser and advance the winner.

        IMPORTANT: pass the **winner's** entrantId. Start.gg auto-marks the
        opposing slot DQ. The `isDQ: true` flag is required — without it, this
        records as a plain 0-0 winner-only report and the loser is NOT flagged
        as DQ'd in standings/exports.
        """
        if str(set_id).startswith("preview"):
            print(f"[STARTGG] Cannot DQ preview set {set_id}")
            return False

        # Ensure ACTIVE — DQ also requires a reportable state.
        try:
            state = await self.fetch_set_state(set_id)
            if state in (None, 1):  # CREATED or unknown — try to advance
                await self.mark_in_progress(set_id)
        except Exception as e:
            print(f"[STARTGG] DQ pre-flight failed for {set_id}: {e}")

        from backend.core.providers.startgg.queries import MARK_SET_DQ
        try:
            await self.query(MARK_SET_DQ, {"setId": set_id, "winnerId": winner_id})
            return True
        except Exception as e:
            print(f"Failed to mark DQ: {e}")
            return False

    async def mark_set_double_dq(self, set_id: str, entrant1_id: str, entrant2_id: str) -> bool:
        """Resolve a double no-show set on Start.gg.

        Start.gg's reportBracketSet requires a winnerId, so a single set cannot
        flag BOTH entrants DQ in one mutation. We DQ entrant2 (entrant1 advances
        as the technical winner) purely so the set CLOSES and the bracket keeps
        moving — the caller is responsible for recording both as DQ locally and
        alerting the TO that the advanced slot may need handling upstream.
        """
        if str(set_id).startswith("preview"):
            print(f"[STARTGG] Cannot double-DQ preview set {set_id}")
            return False

        # Ensure ACTIVE — a report requires a reportable state.
        try:
            state = await self.fetch_set_state(set_id)
            if state in (None, 1):  # CREATED or unknown — try to advance
                await self.mark_in_progress(set_id)
        except Exception as e:
            print(f"[STARTGG] double-DQ pre-flight failed for {set_id}: {e}")

        from backend.core.providers.startgg.queries import MARK_SET_DQ
        try:
            await self.query(MARK_SET_DQ, {"setId": set_id, "winnerId": entrant1_id})
            return True
        except Exception as e:
            print(f"Failed to double-DQ: {e}")
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

    async def fetch_streams(self, slug: str) -> list:
        """Fetch streams configured on a tournament (raw start.gg shape)."""
        from backend.core.providers.startgg.queries import TOURNAMENT_STREAMS
        data = await self.query(TOURNAMENT_STREAMS, {"slug": slug})
        return ((data or {}).get("tournament") or {}).get("streams") or []

    async def assign_stream(self, set_id: str, stream_id: str) -> bool:
        """Assign a set to a start.gg stream queue."""
        if str(set_id).startswith("preview"):
            print(f"[STARTGG] Cannot assign preview set {set_id} to stream")
            return False
        from backend.core.providers.startgg.queries import ASSIGN_STREAM
        try:
            await self.query(ASSIGN_STREAM, {"setId": set_id, "streamId": stream_id})
            return True
        except Exception as e:
            print(f"Failed to assign stream: {e}")
            return False

    async def remove_stream(self, set_id: str) -> bool:
        """Remove a set from the start.gg stream queue."""
        if str(set_id).startswith("preview"):
            return False
        from backend.core.providers.startgg.queries import REMOVE_STREAM
        try:
            await self.query(REMOVE_STREAM, {"setId": set_id})
            return True
        except Exception as e:
            print(f"Failed to remove stream: {e}")
            return False

    async def fetch_user_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Fetch a start.gg user by URL slug. Returns the raw `user` node or None.

        Used by bio-code verification to read the user's bio and confirm they
        added the temporary verification code we issued.
        """
        from backend.core.providers.startgg.queries import USER_BY_SLUG
        try:
            data = await self.query(USER_BY_SLUG, {"slug": slug})
            return (data or {}).get("user")
        except Exception as e:
            print(f"Failed to fetch user by slug '{slug}': {e}")
            return None

    async def probe_token_permissions(self) -> Dict[str, Any]:
        """Verify token validity and check for tournament admin / write permissions."""
        # Ensure we have a token (fetch from DB if needed and cache it)
        if not self.token:
            from backend.core.database import get_setting, get_connection
            self.token = await get_setting("STARTGG_API_TOKEN") or await get_connection("STARTGG_API_TOKEN")

        if not self.token:
            return {
                "valid": False,
                "has_write_scope": False,
                "error": "No Start.gg API token configured."
            }

        # 1. Probe basic token validity (currentUser query)
        current_user_query = """
        query {
          currentUser {
            id
            name
          }
        }
        """
        try:
            user_data = await self.query(current_user_query)
            if not user_data or not user_data.get("currentUser"):
                return {
                    "valid": False,
                    "has_write_scope": False,
                    "error": "Token query succeeded but returned no user. Is the token expired or invalid?"
                }
            user_name = user_data["currentUser"].get("name") or f"User ID {user_data['currentUser'].get('id')}"
        except Exception as e:
            return {
                "valid": False,
                "has_write_scope": False,
                "error": f"Invalid token or network failure: {str(e)}"
            }

        # 2. Probe write permissions (TO mutations).
        # We attempt a safe, dummy markSetInProgress mutation with a non-existent ID.
        # - If the token owner is NOT authorized to mutate start.gg (lacks TO scope),
        #   start.gg immediately rejects at the authorization layer: "You do not have permission to do that".
        # - If the token owner HAS write scope/TO rights, the auth gate passes, and the mutation
        #   fails at the database level: "Set not found" or "record not found".
        probe_mutation = """
        mutation ProbeWriteScope {
          markSetInProgress(setId: "9999999999") {
            id
          }
        }
        """
        try:
            await self.query(probe_mutation)
            # This should raise an error as setId 9999999999 doesn't exist
            # But if it somehow succeeds, it means write scope is present!
            return {
                "valid": True,
                "user_name": user_name,
                "has_write_scope": True,
                "error": None
            }
        except Exception as e:
            err_msg = str(e).lower()
            if "permission" in err_msg or "not authorized" in err_msg or "unauthorized" in err_msg or "token lacks" in err_msg:
                return {
                    "valid": True,
                    "user_name": user_name,
                    "has_write_scope": False,
                    "error": "Token is valid but lacks tournament admin / T.O. write scopes on Start.gg."
                }
            else:
                # Bypassed authorization gate, failed on data lookup! This confirms write/TO scope!
                return {
                    "valid": True,
                    "user_name": user_name,
                    "has_write_scope": True,
                    "error": None
                }

