import os, json, httpx
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sys, copy, shutil

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import (
    init_db, create_or_update_player, get_player,
    save_overlay, get_overlays, delete_overlay,
    upsert_tournament, get_tournaments, get_tournament, delete_tournament, update_tournament_settings,
    save_match_result, get_match_results,
    get_stations, create_station, update_station, delete_station,
    get_station_overlays, add_station_overlay, remove_station_overlay,
    get_active_matches, get_active_match, upsert_active_match, delete_active_match, sync_active_matches, delete_tournament_active_matches,
    get_player_override, save_player_override, get_all_player_overrides, delete_player_override, delete_all_player_overrides,
    add_conflict, get_conflicts, resolve_conflict,
    add_bot_feed, get_bot_feed, clear_bot_feed
)

from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI()

# ── Dynamic Config Helper ───────────────────────────────────────────
async def get_config(key: str, default: str = None) -> str:
    from core.database import get_connection
    # Try DB first
    val = await get_connection(key)
    if val: return val
    # Fallback to env
    return os.getenv(key, default)

@app.on_event("startup")
async def startup_event():
    await init_db()
    # Auto-migrate important env vars to DB if not already there
    from core.database import get_connection, set_connection
    important_vars = ["STARTGG_API_TOKEN", "DISCORD_BOT_TOKEN", "GEMINI_API_KEY", "MATCH_CALL_CHANNEL_ID", "STARTGG_CLIENT_ID", "AI_PROVIDER", "AI_MODEL"]
    for v in important_vars:
        db_val = await get_connection(v)
        env_val = os.getenv(v)
        if not db_val and env_val:
            await set_connection(v, env_val)
    print("✅ Startup: Config migrated to DB")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(__file__)
templates_dir = os.path.join(BASE_DIR, "templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

assets_dir = os.path.join(os.path.dirname(BASE_DIR), "assets")
os.makedirs(assets_dir, exist_ok=True)
app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

avatars_dir = os.path.join(static_dir, "avatars")
os.makedirs(avatars_dir, exist_ok=True)

configs_dir = os.path.join(BASE_DIR, "overlay_configs")
os.makedirs(configs_dir, exist_ok=True)

# ── WebSocket Managers ─────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}
    async def connect(self, slot: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(slot, []).append(ws)
    def disconnect(self, slot: str, ws: WebSocket):
        if ws in self.connections.get(slot, []):
            self.connections[slot].remove(ws)
    async def broadcast(self, slot: str, msg: str):
        for ws in list(self.connections.get(slot, [])):
            try: await ws.send_text(msg)
            except: pass

class HubManager:
    def __init__(self):
        self.clients: list[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)
    def disconnect(self, ws: WebSocket):
        if ws in self.clients: self.clients.remove(ws)
    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        for ws in list(self.clients):
            try: await ws.send_text(msg)
            except: pass

overlay_mgr = ConnectionManager()
hub_mgr = HubManager()

# ── Overlay Config ─────────────────────────────────────────────────────
def _slot_path(slot: str) -> str:
    return os.path.join(configs_dir, f"{slot.replace(' ','_').replace('/','_')}.json")

def _default_elements() -> dict:
    return {
        "p1_name":          {"type":"text","x":400,"y":950,"fontSize":"48","color":"#ffffff","text":"Player 1","visible":True},
        "p2_name":          {"type":"text","x":1520,"y":950,"fontSize":"48","color":"#ffffff","text":"Player 2","visible":True},
        "p1_score":         {"type":"text","x":800,"y":950,"fontSize":"64","color":"#ff0000","text":"0","visible":True},
        "p2_score":         {"type":"text","x":1120,"y":950,"fontSize":"64","color":"#ff0000","text":"0","visible":True},
        "p1_team":          {"type":"text","x":400,"y":900,"fontSize":"24","color":"#aaaaaa","text":"[TEAM]","visible":False},
        "p2_team":          {"type":"text","x":1520,"y":900,"fontSize":"24","color":"#aaaaaa","text":"[TEAM]","visible":False},
        "tournament_round": {"type":"text","x":960,"y":50,"fontSize":"32","color":"#ffffff","text":"Winners Semis","visible":True},
        "tournament_name":  {"type":"text","x":960,"y":100,"fontSize":"24","color":"#aaaaaa","text":"Tournament","visible":False},
        "p1_avatar":        {"type":"image","x":250,"y":850,"width":180,"height":180,"src":"/static/player_placeholder.jpg","visible":True},
        "p2_avatar":        {"type":"image","x":1670,"y":850,"width":180,"height":180,"src":"/static/player_placeholder.jpg","visible":True},
        "p1_flag":          {"type":"image","x":250,"y":980,"width":120,"height":80,"src":"/static/flag_placeholder.png","visible":False},
        "p2_flag":          {"type":"image","x":1670,"y":980,"width":120,"height":80,"src":"/static/flag_placeholder.png","visible":False},
    }

async def resolve_dynamic_overlay(slot: str, config: dict) -> dict:
    """Merges static overlay config with dynamic match data and player overrides."""
    matches = await get_active_matches()
    overrides = await get_all_player_overrides()
    
    # Selection logic: 
    # If slot is 'default', pick the first active match.
    # Otherwise, try to find a match specifically assigned to this slot/station.
    match = None
    if slot == "default":
        match = matches[0] if matches else None
    else:
        # Check if any match is assigned to a station with this name/ID
        match = next((m for m in matches if m.get("station_id") == slot), None)
        if not match:
            match = matches[0] if matches else None

    if not match:
        return config
        
    res = copy.deepcopy(config)
    els = res.get("elements", {})
    
    # Base extracted values (respecting overrides)
    p1_val_name = match.get("p1_name", "Player 1")
    p2_val_name = match.get("p2_name", "Player 2")
    p1_val_score = str(match.get("p1_score", 0))
    p2_val_score = str(match.get("p2_score", 0))
    p1_val_team = match.get("p1_team", "")
    p2_val_team = match.get("p2_team", "")
    p1_val_avatar = "/static/player_placeholder.jpg"
    p2_val_avatar = "/static/player_placeholder.jpg"
    p1_val_flag = ""
    p2_val_flag = ""

    p1_eid = match.get("p1_entrant_id")
    p2_eid = match.get("p2_entrant_id")

    if p1_eid and p1_eid in overrides:
        ov = overrides[p1_eid]
        if ov.get("name"): p1_val_name = ov["name"]
        if ov.get("team"): p1_val_team = ov["team"]
        if ov.get("avatar_url"): p1_val_avatar = ov["avatar_url"]
        if ov.get("country") and len(ov["country"]) == 2:
            p1_val_flag = f"https://flagcdn.com/w160/{ov['country'].lower()}.png"

    if p2_eid and p2_eid in overrides:
        ov = overrides[p2_eid]
        if ov.get("name"): p2_val_name = ov["name"]
        if ov.get("team"): p2_val_team = ov["team"]
        if ov.get("avatar_url"): p2_val_avatar = ov["avatar_url"]
        if ov.get("country") and len(ov["country"]) == 2:
            p2_val_flag = f"https://flagcdn.com/w160/{ov['country'].lower()}.png"

    swap = match.get("swapped", False)

    # Now assign based on swapped flag
    if swap:
        mapping = {
            "p1_name": p2_val_name,
            "p2_name": p1_val_name,
            "p1_score": p2_val_score,
            "p2_score": p1_val_score,
            "p1_team": p2_val_team,
            "p2_team": p1_val_team,
            "tournament_round": match.get("round_name", ""),
        }
        avatars = {"p1_avatar": p2_val_avatar, "p2_avatar": p1_val_avatar}
        flags = {"p1_flag": p2_val_flag, "p2_flag": p1_val_flag}
    else:
        mapping = {
            "p1_name": p1_val_name,
            "p2_name": p2_val_name,
            "p1_score": p1_val_score,
            "p2_score": p2_val_score,
            "p1_team": p1_val_team,
            "p2_team": p2_val_team,
            "tournament_round": match.get("round_name", ""),
        }
        avatars = {"p1_avatar": p1_val_avatar, "p2_avatar": p2_val_avatar}
        flags = {"p1_flag": p1_val_flag, "p2_flag": p2_val_flag}

    for k, v in mapping.items():
        if k in els: els[k]["text"] = v

    for k, v in avatars.items():
        if k in els and v != "/static/player_placeholder.jpg":
            els[k]["src"] = v

    for k, v in flags.items():
        if k in els and v:
            els[k]["src"] = v
            els[k]["visible"] = True
            
    return res

def load_overlay_config(slot: str = "default") -> dict:
    defaults = {"background_url":"","global_font_url":"https://fonts.googleapis.com/css2?family=Cairo:wght@200..1000&display=swap","global_font_family":"'Cairo', sans-serif","elements":_default_elements()}
    path = _slot_path(slot)
    if os.path.exists(path):
        with open(path) as f: data = json.load(f)
        if "elements" not in data: data["elements"] = {}
        return data
    return defaults

def save_overlay_config(slot: str, data: dict):
    with open(_slot_path(slot), "w") as f: json.dump(data, f)

# ── Start.gg ───────────────────────────────────────────────────────────
STARTGG_API_URL = "https://api.start.gg/gql/alpha"

TOURNAMENT_QUERY = """query($slug:String!){tournament(slug:$slug){id name events{id name videogame{name}entrants(query:{perPage:100}){nodes{id name}}}}}"""
# state: 1=Not Started, 2=On Going, 3=Complete, 6=DQ
SETS_QUERY = """
query($eventId:ID!){
  event(id:$eventId){
    id
    name
    sets(page:1, perPage:500){
      nodes{
        id state displayScore fullRoundText
        identifier
        phaseGroup{ id displayIdentifier }
        slots{
          entrant{
            id name
            participants{
              player{ user{ slug } }
              gamerTag
            }
          }
        }
      }
    }
  }
}
"""
REPORT_SET_MUTATION = """mutation($setId:ID!,$winnerId:ID!,$gameData:[BracketSetGameDataInput]){reportBracketSet(setId:$setId,winnerId:$winnerId,gameData:$gameData){id state}}"""
REPORT_SET_DQ_MUTATION = """mutation($setId:ID!,$winnerId:ID,$isDQ:Boolean,$gameData:[BracketSetGameDataInput]){updateBracketSet(setId:$setId,winnerId:$winnerId,isDQ:$isDQ,gameData:$gameData){id state displayScore}}"""
RESET_SET_MUTATION = """mutation($setId:ID!){resetSet(setId:$setId,resetDependentSets:true){id state}}"""
MARK_IN_PROGRESS_MUTATION = """mutation($setId:ID!){markSetInProgress(setId:$setId){id state}}"""

async def startgg_gql(query: str, variables: dict) -> dict:
    token = await get_config("STARTGG_API_TOKEN")
    if not token: return {"error": "STARTGG_API_TOKEN not set"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(STARTGG_API_URL, json={"query":query,"variables":variables},
                                 headers={"Authorization":f"Bearer {token}"}, timeout=15)
        print(f"[STARTGG] GQL Response Status: {resp.status_code}")
        try:
            res = resp.json()
            if "errors" in res:
                print(f"[STARTGG] GQL Errors: {res['errors']}")
            return res
        except Exception as e:
            print(f"[STARTGG] GQL Parse Error: {e}, Body: {resp.text}")
            return {"error": "Invalid JSON response"}

# ── Startup ────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    await init_db()

# ── Pages ──────────────────────────────────────────────────────────────
@app.get("/admin/hub")
async def page_hub(request: Request): return templates.TemplateResponse(request=request, name="hub.html")
@app.get("/admin/editor")
async def page_editor(request: Request): return templates.TemplateResponse(request=request, name="editor.html")
@app.get("/obs")
async def page_obs(request: Request): return templates.TemplateResponse(request=request, name="obs.html")

# ── Auth (unchanged) ──────────────────────────────────────────────────
@app.get("/login")
async def login(discord_id: str):
    client_id = await get_config("STARTGG_CLIENT_ID")
    api_base = await get_config("API_BASE_URL", "http://localhost:8000")
    redirect_uri = f"{api_base}/callback"
    return RedirectResponse(url=f"https://start.gg/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state={discord_id}")

@app.get("/callback")
async def callback(code: str, state: str):
    discord_id = state
    await create_or_update_player(discord_id=discord_id, startgg_id="demo", gamer_tag="DemoGamer", is_verified=True)
    return {"message": f"Linked to Discord ID {discord_id}."}

# ── Overlay DB Profiles (Legacy/Hub) ──────────────────────────────────
@app.get("/api/overlays-db")
async def api_get_overlays_db(): return {"overlays": await get_overlays()}

@app.post("/api/overlays")
async def api_save_overlay(request: Request):
    d = await request.json()
    if not d.get("name") or not d.get("config"): raise HTTPException(400)
    # Save both to DB and File for compatibility
    await save_overlay(d["name"], json.dumps(d["config"]))
    save_overlay_config(d["name"], d["config"])
    return {"message": "Saved"}

@app.delete("/api/overlays/{name}")
async def api_delete_overlay(name: str):
    await delete_overlay(name)
    path = _slot_path(name)
    if os.path.exists(path): os.remove(path)
    return {"message": "Deleted"}

# ── Overlay State per slot ─────────────────────────────────────────────
@app.get("/api/overlay-state/{slot}")
async def api_overlay_state(slot: str): return load_overlay_config(slot)

# ── Player Avatar ──────────────────────────────────────────────────────
@app.get("/api/player/{discord_id}/avatar")
async def api_player_avatar(discord_id: str):
    p = await get_player(discord_id)
    if p and p.get("avatar_path") and os.path.exists(p["avatar_path"]):
        return FileResponse(p["avatar_path"])
    return FileResponse(os.path.join(static_dir, "player_placeholder.jpg"))

# ── Tournaments ────────────────────────────────────────────────────────
@app.get("/api/tournaments")
async def api_list_tournaments(): return {"tournaments": await get_tournaments()}

@app.post("/api/tournaments")
async def api_add_tournament(request: Request):
    slug = (await request.json()).get("slug","").strip()
    if not slug: raise HTTPException(400, "Slug required")
    
    # Extract slug if it's a URL
    # Handle patterns: https://www.start.gg/tournament/slug/..., start.gg/tournament/slug, etc.
    if "start.gg/" in slug:
        parts = slug.split("start.gg/")[-1].split("/")
        if "tournament" in parts:
            idx = parts.index("tournament")
            if len(parts) > idx + 1:
                slug = parts[idx + 1]
        elif "admin/tournament" in slug:
            # handle admin URLs
            parts = slug.split("admin/tournament/")[-1].split("/")
            if len(parts) > 0:
                slug = parts[0]
        else:
            # Fallback: take the first part after start.gg/ if it's not 'tournament'
            slug = parts[0]
    
    # Final cleanup: remove trailing slashes
    slug = slug.strip("/")

    result = await startgg_gql(TOURNAMENT_QUERY, {"slug": slug})
    print(f"[API] add_tournament result: {result}")
    if "error" in result or "errors" in result:
        print(f"[API] Error adding tournament: {result.get('error') or result.get('errors')}")
        await upsert_tournament(slug=slug, name=f"[Mock] {slug}", event_name="Event 1", event_id="0", game="Street Fighter 6",
                                raw_data=json.dumps({"mock":True,"entrants":[{"name":"Player A","id":"m1"},{"name":"Player B","id":"m2"}]}))
        return {"message":"Saved with mock data","mock":True}
    t = result.get("data",{}).get("tournament")
    if not t:
        print(f"[API] Tournament not found on Start.gg for slug: {slug}")
        raise HTTPException(404, "Not found on Start.gg")
    
    events = t.get("events", [])
    print(f"[API] Found {len(events)} events for {slug}")
    for ev_item in events:
        print(f"  - Event: {ev_item.get('name')} (ID: {ev_item.get('id')})")
        
    ev = events[0] if events else {}
    await upsert_tournament(slug=slug, name=t["name"], event_name=ev.get("name",""), event_id=str(ev.get("id","")),
                            game=ev.get("videogame",{}).get("name",""), raw_data=json.dumps(result["data"]))
    return {"message": f"'{t['name']}' added."}

@app.get("/api/tournaments/{slug}/refresh")
async def api_refresh_tournament(slug: str):
    result = await startgg_gql(TOURNAMENT_QUERY, {"slug": slug})
    t = result.get("data",{}).get("tournament")
    if not t: return {"message":"Refresh failed","ok":False}
    ev = t["events"][0] if t.get("events") else {}
    await upsert_tournament(slug=slug, name=t["name"], event_name=ev.get("name",""), event_id=str(ev.get("id","")),
                            game=ev.get("videogame",{}).get("name",""), raw_data=json.dumps(result["data"]))
    return {"message":"Refreshed","ok":True}

@app.post("/api/tournaments/{slug}/reset-hub")
async def api_reset_tournament_hub(slug: str):
    """Force wipes all local active matches for this tournament."""
    await delete_tournament_active_matches(slug)
    await hub_mgr.broadcast({"type": "match_update"})
    await add_bot_feed(f"🔄 Admin force-reset all local match data for tournament: {slug}", "warn")
    return {"message": "Hub matches reset", "ok": True}

@app.get("/api/tournaments/{slug}/sets")
async def api_get_sets(slug: str):
    t = await get_tournament(slug)
    if not t or not t.get("event_id") or t["event_id"] == "0":
        return {"sets":[
            {"id":"mock_1","state":1,"round":"Winners R1","p1":"Player A","p2":"Player B","p1_eid":"m1","p2_eid":"m2"},
            {"id":"mock_2","state":2,"round":"Losers R1","p1":"Player C","p2":"Player D","p1_eid":"m3","p2_eid":"m4"}],
            "mock":True}
    print(f"[API] Fetching sets for tournament: {slug}, event_id: {t.get('event_id')}")
    result = await startgg_gql(SETS_QUERY, {"eventId": t["event_id"]})
    
    if "errors" in result:
        print(f"[API] Start.gg GQL Errors: {result['errors']}")
    
    data = result.get("data")
    if not data or not data.get("event"):
        print(f"[API] Event not found or Data null: {result}")
        return {"sets":[], "error": "Event not found on Start.gg"}
    
    nodes = data["event"].get("sets", {}).get("nodes", [])
    print(f"[API] Found {len(nodes)} sets on Start.gg for event {t['event_id']}")
    
    # Sync with local active matches (Source of Truth: Start.gg)
    if nodes:
        await sync_active_matches(slug, nodes)
    
    # Fetch all overrides
    overrides = await get_all_player_overrides()
    
    sets = []
    for s in nodes:
        sl = s.get("slots",[])
        p1e = sl[0].get("entrant") or {} if len(sl)>0 else {}
        p2e = sl[1].get("entrant") or {} if len(sl)>1 else {}
        
        p1_eid = str(p1e.get("id",""))
        p2_eid = str(p2e.get("id",""))
        
        # Apply overrides
        p1_name = overrides.get(p1_eid, {}).get("name") or p1e.get("name","TBD")
        p2_name = overrides.get(p2_eid, {}).get("name") or p2e.get("name","TBD")
        p1_team = overrides.get(p1_eid, {}).get("team")
        p2_team = overrides.get(p2_eid, {}).get("team")
        
        # Try to extract gamer tag from participants
        p1_tag = ""
        p2_tag = ""
        if p1e.get("participants"):
            p1_tag = p1e["participants"][0].get("gamerTag", "") if p1e["participants"] else ""
        if p2e.get("participants"):
            p2_tag = p2e["participants"][0].get("gamerTag", "") if p2e["participants"] else ""
            
        # Extract phaseGroup info
        pg = s.get("phaseGroup") or {}
        pg_name = pg.get("displayIdentifier") or ""
        # Detect DQ (State 6)
        is_dq = s.get("state") == 6
        
        sets.append({
            "id": str(s["id"]),
            "identifier": s.get("identifier"),
            "state": s.get("state"),
            "score": s.get("displayScore"),
            "round": s.get("fullRoundText",""),
            "p1": p1_name,
            "p2": p2_name,
            "p1_team": p1_team,
            "p2_team": p2_team,
            "p1_tag": p1_tag,
            "p2_tag": p2_tag,
            "p1_eid": p1_eid,
            "p2_eid": p2_eid,
            "phaseGroup": pg_name,
            "isDQ": is_dq
        })
    return {"sets": sets}

@app.delete("/api/tournaments/{slug}")
async def api_delete_tournament(slug: str):
    await delete_tournament(slug); return {"message":"Deleted"}

@app.patch("/api/tournaments/{slug}/settings")
async def api_update_tournament_settings(slug: str, request: Request):
    d = await request.json()
    allowed = {"dq_timer_seconds", "auto_dq_enabled"}
    filtered = {k: v for k, v in d.items() if k in allowed}
    if filtered:
        await update_tournament_settings(slug, **filtered)
    return {"message": "Updated"}

# ── Stations ───────────────────────────────────────────────────────────
@app.get("/api/stations")
async def api_get_stations():
    stations = await get_stations()
    for st in stations:
        st["overlays"] = await get_station_overlays(st["id"])
    return {"stations": stations}

@app.post("/api/stations")
async def api_create_station(request: Request):
    d = await request.json()
    sid = d.get("id","").strip(); name = d.get("name","").strip()
    if not sid or not name: raise HTTPException(400)
    await create_station(sid, name); return {"message":"Created"}

@app.patch("/api/stations/{sid}")
async def api_update_station(sid: str, request: Request):
    d = await request.json()
    await update_station(sid, **d); return {"message":"Updated"}

@app.delete("/api/stations/{sid}")
async def api_delete_station(sid: str):
    await delete_station(sid); return {"message":"Deleted"}

@app.post("/api/stations/{sid}/overlays")
async def api_add_station_overlay(sid: str, request: Request):
    d = await request.json()
    await add_station_overlay(sid, d["overlay_name"]); return {"message":"Added"}

@app.delete("/api/stations/{sid}/overlays/{oname}")
async def api_remove_station_overlay(sid: str, oname: str):
    await remove_station_overlay(sid, oname); return {"message":"Removed"}

# ── Active Matches ─────────────────────────────────────────────────────
@app.get("/api/active-matches")
async def api_active_matches(tournament_slug: str = None):
    matches = await get_active_matches(tournament_slug)
    overrides = await get_all_player_overrides()
    
    for m in matches:
        p1_eid = m.get("p1_entrant_id")
        p2_eid = m.get("p2_entrant_id")
        if p1_eid and p1_eid in overrides:
            ov = overrides[p1_eid]
            if ov.get("name"): m["p1_name"] = ov["name"]
            if ov.get("team"): m["p1_team"] = ov["team"]
            if ov.get("country"): m["p1_country"] = ov["country"]
            if ov.get("cfn"): m["p1_cfn"] = ov["cfn"]
            if ov.get("avatar_url"): m["p1_avatar_url"] = ov["avatar_url"]
        if p2_eid and p2_eid in overrides:
            ov = overrides[p2_eid]
            if ov.get("name"): m["p2_name"] = ov["name"]
            if ov.get("team"): m["p2_team"] = ov["team"]
            if ov.get("country"): m["p2_country"] = ov["country"]
            if ov.get("cfn"): m["p2_cfn"] = ov["cfn"]
            if ov.get("avatar_url"): m["p2_avatar_url"] = ov["avatar_url"]
            
    return {"matches": matches}

@app.post("/api/active-matches")
async def api_create_active_match(request: Request):
    d = await request.json()
    await upsert_active_match(d["set_id"], **{k:v for k,v in d.items() if k!="set_id"})
    await hub_mgr.broadcast({"type":"match_update"})
    await broadcast_overlay_updates()
    return {"message":"Created"}

@app.post("/api/active-matches/{set_id}/call")
async def api_call_match(set_id: str, request: Request):
    """Admin calls players for this match. Sets called_at, status→called, triggers bot."""
    d = await request.json() if request.headers.get("content-length","0") != "0" else {}
    m = await get_active_match(set_id)
    if not m: raise HTTPException(404)
    import datetime
    called_at = datetime.datetime.utcnow().isoformat()
    await upsert_active_match(set_id, status="called", called_at=called_at,
                              p1_ready=False, p2_ready=False)
    # Notify bot via hub command to trigger Discord DMs
    from core.database import add_hub_command
    await add_hub_command(f"call_match {set_id}")
    await add_bot_feed(f"📢 Players called for match #{m.get('match_number', set_id)}: {m['p1_name']} vs {m['p2_name']}")
    await hub_mgr.broadcast({"type": "match_update"})
    return {"message": "Players called", "called_at": called_at}

@app.post("/api/active-matches/{set_id}/player-ready")
async def api_player_ready(set_id: str, request: Request):
    """Mark a player as ready. If both ready, auto-advance to in_progress."""
    d = await request.json()
    player = d.get("player")  # 'p1' or 'p2'
    if player not in ("p1", "p2"): raise HTTPException(400, "player must be p1 or p2")
    m = await get_active_match(set_id)
    if not m: raise HTTPException(404)
    update = {f"{player}_ready": True}
    await upsert_active_match(set_id, **update)
    m = await get_active_match(set_id)  # re-fetch
    p1r = m.get("p1_ready"); p2r = m.get("p2_ready")
    if p1r and p2r:
        # Both ready — advance to in_progress
        import datetime
        started_at = datetime.datetime.utcnow().isoformat()
        await upsert_active_match(set_id, status="in_progress", started_at=started_at)
        # Try markSetInProgress on Start.gg
        sgg = await startgg_gql(MARK_IN_PROGRESS_MUTATION, {"setId": set_id})
        await add_bot_feed(f"✅ Both players ready for match #{m.get('match_number', set_id)} — In Progress")
        await hub_mgr.broadcast({"type": "match_update"})
        return {"message": "Both ready — match in progress", "both_ready": True, "startgg": sgg}
    await hub_mgr.broadcast({"type": "match_update"})
    return {"message": f"{player} marked ready", "both_ready": False}

@app.patch("/api/active-matches/{set_id}/stream")
async def api_toggle_stream(set_id: str, request: Request):
    """Toggle stream match flag."""
    d = await request.json()
    is_stream = bool(d.get("is_stream_match", False))
    await upsert_active_match(set_id, is_stream_match=is_stream)
    await hub_mgr.broadcast({"type": "match_update"})
    return {"message": "Stream flag updated"}

@app.patch("/api/active-matches/{set_id}")
async def api_update_active_match(set_id: str, request: Request):
    d = await request.json()
    if d.get("status") == "in_progress" and "started_at" not in d:
        import datetime
        d["started_at"] = datetime.datetime.utcnow().isoformat()
    await upsert_active_match(set_id, **d)
    m = await get_active_match(set_id)
    # Push to overlay if station assigned
    await broadcast_overlay_updates()
    await hub_mgr.broadcast({"type":"match_update"})
    return {"message":"Updated"}

@app.delete("/api/active-matches/{set_id}")
async def api_delete_active_match(set_id: str):
    await delete_active_match(set_id)
    await hub_mgr.broadcast({"type":"match_update"})
    return {"message":"Deleted"}

@app.post("/api/active-matches/{set_id}/send")
async def api_send_match(set_id: str):
    """Report score to Start.gg and mark complete."""
    m = await get_active_match(set_id)
    if not m: raise HTTPException(404)
    p1_score = int(m.get("p1_score") or 0)
    p2_score = int(m.get("p2_score") or 0)
    p1_eid = m.get("p1_entrant_id")
    p2_eid = m.get("p2_entrant_id")
    winner_eid = p1_eid if p1_score > p2_score else p2_eid
    winner_name = m.get("p1_name") if p1_score > p2_score else m.get("p2_name")
    
    if not winner_eid:
        raise HTTPException(status_code=400, detail="Cannot send match: missing player entrant ID")
        
    game_data = []
    for _ in range(p1_score):
        game_data.append({"gameNum": len(game_data) + 1, "winnerId": p1_eid})
    for _ in range(p2_score):
        game_data.append({"gameNum": len(game_data) + 1, "winnerId": p2_eid})
        
    # Try Start.gg
    result = await startgg_gql(REPORT_SET_MUTATION, {"setId": set_id, "winnerId": winner_eid, "gameData": game_data})
    
    # Check for Start.gg API errors
    if "errors" in result:
        return {"message": f"Start.gg Error: {result['errors'][0].get('message', 'Unknown error')}", "error": True}
        
    await upsert_active_match(set_id, status="complete")
    await save_match_result(set_id, m.get("tournament_slug",""), m.get("station_id",""),
                            m["p1_name"], m["p2_name"], winner_name, str(p1_score), str(p2_score), m.get("round_name",""))
    
    match_label = m.get("match_number") or m.get("identifier") or set_id
    completion_msg = f"Match #{match_label} completed: {winner_name} wins {p1_score}-{p2_score}"
    await add_bot_feed(completion_msg)
    # Announce to Discord
    from core.database import add_hub_command
    await add_hub_command(f"announce {completion_msg}")
    
    await hub_mgr.broadcast({"type":"match_update"})
    return {"message":"Sent","startgg_response": result}

@app.post("/api/active-matches/{set_id}/dq")
async def api_dq_match(set_id: str, request: Request):
    d = await request.json()
    dq_player = d.get("player")  # "p1", "p2", or "both"
    m = await get_active_match(set_id)
    if not m: raise HTTPException(404)
    
    dq_name = ""
    winner_name = ""
    winner_eid = ""
    game_data = None
    
    if dq_player == "p1":
        dq_name = m["p1_name"]
        winner_name = m["p2_name"]
        winner_eid = m["p2_entrant_id"]
    elif dq_player == "p2":
        dq_name = m["p2_name"]
        winner_name = m["p1_name"]
        winner_eid = m["p1_entrant_id"]
    elif dq_player == "both":
        dq_name = "Both players"
        winner_name = "None (Double DQ)"
        # For Double DQ, we MUST pick a winner for the API to close the set, 
        # but -1/-1 scores tell Start.gg it's a double loss.
        winner_eid = m["p1_entrant_id"]
        game_data = [{"winnerId": m["p1_entrant_id"], "entrant1Score": -1, "entrant2Score": -1}]

    if dq_player == "both" or winner_eid:
        # Call the DQ mutation (updateBracketSet)
        await startgg_gql(REPORT_SET_DQ_MUTATION, {
            "setId": set_id,
            "winnerId": winner_eid,
            "isDQ": True,
            "gameData": game_data
        })

    await upsert_active_match(set_id, status="dq")
    await save_match_result(set_id, m.get("tournament_slug",""), m.get("station_id",""),
                            m["p1_name"], m["p2_name"], winner_name, "0", "0", m.get("round_name",""))
    
    await add_bot_feed(f"DQ: {dq_name} disqualified from match #{m.get('match_number',set_id)}", "warn")
    await hub_mgr.broadcast({"type":"match_update"})
    await broadcast_overlay_updates()
    return {"message": f"{dq_name} DQ'd on Start.gg and locally"}

@app.post("/api/active-matches/{set_id}/reset")
async def api_reset_match(set_id: str):
    """Reset match on Start.gg and remove from local active matches."""
    # 1. Try Reset on Start.gg
    result = await startgg_gql(RESET_SET_MUTATION, {"setId": set_id})
    if "errors" in result:
        return {"message": f"Start.gg Reset Error: {result['errors'][0].get('message', 'Unknown error')}", "error": True}
    # 2. Delete local record if exists
    await delete_active_match(set_id)
    # 3. Broadcast
    await hub_mgr.broadcast({"type":"match_update"})
    return {"message":"Reset successful","startgg_response":result}

# ── Conflicts ──────────────────────────────────────────────────────────
@app.get("/api/conflicts")
async def api_get_conflicts(): return {"conflicts": await get_conflicts(False)}

@app.post("/api/conflicts/{cid}/resolve")
async def api_resolve_conflict(cid: int, request: Request):
    d = await request.json()
    await resolve_conflict(cid, d.get("resolution",""))
    await hub_mgr.broadcast({"type":"conflict_update"})
    return {"message":"Resolved"}

# ── Bot Feed ───────────────────────────────────────────────────────────
@app.get("/api/bot-feed")
async def api_get_feed(): return {"feed": await get_bot_feed(50)}

@app.post("/api/bot-feed")
async def api_post_feed(request: Request):
    d = await request.json()
    await add_bot_feed(d.get("message",""), d.get("level","info"))
    await hub_mgr.broadcast({"type":"bot_feed","message":d.get("message",""),"level":d.get("level","info")})
    return {"message":"Logged"}

@app.delete("/api/bot-feed")
async def api_clear_feed():
    await clear_bot_feed()
    await hub_mgr.broadcast({"type":"match_update"}) # Force refetch
    return {"message":"Cleared"}

@app.post("/api/bot-command")
async def api_bot_command(request: Request):
    d = await request.json()
    cmd = d.get("command", "")
    if cmd:
        from core.database import add_hub_command
        await add_hub_command(cmd)
        await add_bot_feed(f"Admin command: {cmd}", "info")
        await hub_mgr.broadcast({"type":"bot_feed","message":f"Admin command: {cmd}","level":"info"})
    return {"message":"Command queued"}

# ── Settings ───────────────────────────────────────────────────────────────
@app.get("/api/settings")
async def api_get_settings():
    from core.database import get_all_settings
    return {"settings": await get_all_settings()}

@app.patch("/api/settings")
async def api_patch_settings(request: Request):
    from core.database import set_setting
    d = await request.json()
    for k, v in d.items():
        await set_setting(k, str(v))
    return {"message": "Settings updated"}

@app.get("/api/env")
async def api_get_env():
    """Returns non-sensitive env variables from DB (priority) or Env."""
    keys = ["STARTGG_CLIENT_ID", "API_BASE_URL", "MATCH_CALL_CHANNEL_ID", "STARTGG_API_TOKEN", "AI_PROVIDER", "AI_MODEL", "GEMINI_API_KEY"]
    res = {}
    for k in keys:
        val = await get_config(k)
        if (k == "STARTGG_API_TOKEN" or k == "GEMINI_API_KEY") and val:
            res[k] = val[:4] + "****"
        else:
            res[k] = val or ""
    return res

@app.patch("/api/env")
async def api_patch_env(request: Request):
    from core.database import set_connection
    d = await request.json()
    
    for k, v in d.items():
        new_val = str(v).strip()
        # PROTECTION: If the new value is masked (ends with ****) or empty, ignore
        if not new_val.endswith("****") and new_val != "":
            await set_connection(k, new_val)
    
    return {"message": "Connections saved to Database. These will now override .env settings. Click Reconnect to verify."}

# ── Status ─────────────────────────────────────────────────────────────
@app.get("/api/status")
async def api_status():
    from core.database import get_setting
    import datetime
    
    # 1. Start.gg Check
    startgg_ok = False
    try:
        # Simple query to check token validity
        test_q = "query { currentUser { id name } }"
        res = await startgg_gql(test_q, {})
        if res and "data" in res and res["data"].get("currentUser"):
            startgg_ok = True
    except: pass

    # 2. Discord Bot Check (Heartbeat)
    bot_ok = False
    last_seen = await get_setting("bot_last_seen")
    if last_seen:
        try:
            ls_dt = datetime.datetime.fromisoformat(last_seen)
            # Use 60 seconds to be safe
            if (datetime.datetime.now() - ls_dt).total_seconds() < 60:
                bot_ok = True
        except: pass

    return {
        "startgg_api": startgg_ok,
        "discord_bot": bot_ok,
        "websockets": True # If they are reached this far, HTTP is up
    }

@app.post("/api/reconnect")
async def api_reconnect():
    # Just a trigger for the UI to refresh status
    return {"message": "Reconnecting..."}

@app.get("/api/overlays")
async def api_list_overlays():
    """List all saved overlay slot names and their configs."""
    files = [f for f in os.listdir(configs_dir) if f.endswith(".json")]
    out = []
    for f in files:
        slot = f.replace(".json", "").replace("_", " ")
        config = load_overlay_config(slot)
        out.append({"name": slot, "config": config})
    return out

@app.post("/api/overlays/rename")
async def api_rename_overlay(request: Request):
    """Rename an overlay config file."""
    data = await request.json()
    old_name = data.get("old_name")
    new_name = data.get("new_name")
    if not old_name or not new_name:
        raise HTTPException(400, "Missing names")
    
    old_path = _slot_path(old_name)
    new_path = _slot_path(new_name)
    
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        return {"ok": True}
    return {"error": "Not found"}

# ── Match Results ──────────────────────────────────────────────────────
@app.get("/api/match-results")
async def api_match_results(tournament_slug: str = None):
    return {"results": await get_match_results(tournament_slug)}

# ── WebSocket: Overlay (per slot) ─────────────────────────────────────
@app.websocket("/ws/overlay/{slot}")
async def ws_overlay_slot(slot: str, websocket: WebSocket):
    await overlay_mgr.connect(slot, websocket)
    config = load_overlay_config(slot)
    resolved = await resolve_dynamic_overlay(slot, config)
    await websocket.send_text(json.dumps(resolved))
    try:
        while True:
            data = await websocket.receive_text()
            # If the overlay sends data back (from editor), save it as base config
            state = json.loads(data)
            save_overlay_config(slot, state)
            # Re-resolve and broadcast
            resolved = await resolve_dynamic_overlay(slot, state)
            await overlay_mgr.broadcast(slot, json.dumps(resolved))
    except WebSocketDisconnect:
        overlay_mgr.disconnect(slot, websocket)

async def broadcast_overlay_updates():
    """Broadcasts current resolved state to all connected overlays."""
    for slot in list(overlay_mgr.connections.keys()):
        config = load_overlay_config(slot)
        resolved = await resolve_dynamic_overlay(slot, config)
        await overlay_mgr.broadcast(slot, json.dumps(resolved))

@app.websocket("/ws/overlay")
async def ws_overlay_default(websocket: WebSocket):
    await ws_overlay_slot("default", websocket)

# ── WebSocket: Hub ─────────────────────────────────────────────────────
@app.websocket("/ws/hub")
async def ws_hub(websocket: WebSocket):
    await hub_mgr.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub_mgr.disconnect(websocket)

@app.get("/api/players/overrides")
async def api_get_all_player_overrides():
    return await get_all_player_overrides()

@app.get("/api/players/override/{id}")
async def api_get_player_override(id: str):
    ov = await get_player_override(id)
    return ov or {}

@app.patch("/api/players/override/{id}")
async def api_save_player_override(id: str, request: Request):
    data = await request.json()
    await save_player_override(id, data)
    await hub_mgr.broadcast({"type": "match_update"})
    await broadcast_overlay_updates()
    return {"ok": True}

@app.post("/api/players/avatar/{id}")
async def api_upload_player_avatar(id: str, file: UploadFile = File(...)):
    # 1. Size check (e.g., 2MB limit)
    MAX_SIZE = 2 * 1024 * 1024 # 2MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "File too large. Max 2MB allowed.")
    
    # 2. Aspect Ratio check (optional, if Pillow is installed)
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        ratio = w / h
        if ratio < 0.8 or ratio > 1.2:
            # We don't block, but maybe we should?
            # For now, let's just warn or block if you prefer.
            # The user said "check the sizes and aspect ratio", implying enforcement.
            raise HTTPException(400, f"Invalid aspect ratio ({w}x{h}). Please use a square image (roughly 1:1).")
    except ImportError:
        print("[API] Pillow not installed, skipping aspect ratio check.")
    except Exception as e:
        print(f"[API] Image validation error: {e}")
        # If it's not a valid image, Pillow will fail. 
        # But we already have the content, so we can try to save it anyway or block.
        # Let's block if it's not a valid image.
        raise HTTPException(400, "Invalid image file.")

    os.makedirs("backend/api/static/avatars", exist_ok=True)
    ext = file.filename.split(".")[-1]
    filename = f"{id}.{ext}"
    path = os.path.join("backend/api/static/avatars", filename)
    
    with open(path, "wb") as f:
        f.write(content)
    
    avatar_url = f"/static/avatars/{filename}"
    await save_player_override(id, {"avatar_url": avatar_url})
    await hub_mgr.broadcast({"type": "match_update"})
    await broadcast_overlay_updates()
    return {"avatar_url": avatar_url}
