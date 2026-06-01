import os, json
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import init_db, get_setting, get_all_settings, set_setting
from backend.api.ws_manager import manager as ws_manager
from backend.api.routers.players import router as players_router
from backend.api.routers.matches import router as matches_router
from backend.api.routers.tournaments import router as tournaments_router
from backend.api.routers.overlays import router as overlays_router
from backend.api.routers.settings import router as settings_router
from backend.api.routers.hub import router as hub_router
from backend.api.routers.stations import router as stations_router
from backend.api.routers.assets import router as assets_router
from backend.api.routers.auth import router as auth_router
from backend.api.routers.planned_streams import router as planned_streams_router

load_dotenv()

app = FastAPI(
    title="FNC Tournament Organizer API",
    description=(
        "AI-powered match coordination, registration, and overlay management system. "
        "Integrates Discord bot automations with Start.gg bracket management APIs."
    ),
    version="1.0.0",
    servers=[{"url": "http://localhost:8000", "description": "Development Server"}]
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Unified Global Exception Handlers
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "message": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors_str = []
    for err in exc.errors():
        loc = " -> ".join([str(x) for x in err.get("loc", [])])
        msg = err.get("msg", "invalid value")
        errors_str.append(f"{loc}: {msg}")
    error_msg = "; ".join(errors_str)
    return JSONResponse(
        status_code=422,
        content={"error": True, "message": f"Validation error: {error_msg}"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": f"Internal Server Error: {str(exc)}"}
    )

# Routers — prefixes must match what the frontend calls
app.include_router(tournaments_router, prefix="/api/tournaments")
app.include_router(players_router,     prefix="/api/players")
app.include_router(stations_router,    prefix="/api/stations")
app.include_router(overlays_router,    prefix="/api/overlays")
app.include_router(assets_router,      prefix="/api/assets")
app.include_router(auth_router,        prefix="/api/auth")
# These routers define their own sub-paths (/settings, /env, /bot-feed, /active-matches…)
app.include_router(settings_router,    prefix="/api")
app.include_router(hub_router,         prefix="/api")
app.include_router(matches_router,     prefix="/api")
app.include_router(planned_streams_router, prefix="/api")


# Static files
BASE_DIR = os.path.dirname(__file__)
static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Background Tasks & Helper Loops
async def reconciliation_loop():
    """Background task that periodically (every 45s) keeps local active_matches in sync with Start.gg."""
    import asyncio
    from backend.core.database import get_tournaments, sync_active_matches
    from backend.core.providers.registry import get_provider_for_tournament
    from backend.api.ws_manager import manager as hub_mgr

    print("[SYS] Start.gg reconciliation background task started")
    while True:
        try:
            await asyncio.sleep(45)
            tournaments = await get_tournaments()
            for t in tournaments:
                slug = t.get("slug")
                if not slug:
                    continue
                try:
                    provider = await get_provider_for_tournament(slug)
                    provider_sets = await provider.fetch_sets(slug)
                    if provider_sets:
                        await sync_active_matches(slug, provider_sets)
                    # Broadcast updates to hub clients
                    await hub_mgr.broadcast({"type": "match_update"})
                except Exception as e:
                    print(f"[SYS] Reconciliation failed for tournament {slug}: {e}")
        except asyncio.CancelledError:
            print("[SYS] Start.gg reconciliation background task cancelled")
            break
        except Exception as e:
            print(f"[SYS] Error in reconciliation loop: {e}")

# Startup
@app.on_event("startup")
async def startup_event():
    import asyncio
    await init_db()
    # Migration of env to DB
    important_vars = ["STARTGG_API_TOKEN", "DISCORD_BOT_TOKEN", "GOOGLE_API_KEY", "HUB_PASSWORD"]
    all_settings = await get_all_settings()
    for v in important_vars:
        db_val = all_settings.get(v)
        env_val = os.getenv(v)
        if not db_val and env_val:
            await set_setting(v, env_val)
    print("[SYS] API Started and Config Migrated")

    # Run token permission probe on startup in background
    async def run_token_probe():
        try:
            from backend.core.providers.startgg.client import get_client
            client = get_client()
            client.token = None # Force reload from settings/DB
            probe_result = await client.probe_token_permissions()
            await set_setting("token_scope_status", json.dumps(probe_result))
            print(f"[SYS] Start.gg token probe complete: {probe_result}")
        except Exception as e:
            print(f"[SYS] Startup Start.gg token probe failed: {e}")
    
    asyncio.create_task(run_token_probe())

    # Start the periodic reconciliation loop in background
    asyncio.create_task(reconciliation_loop())


# WebSocket Endpoint
@app.websocket("/ws/hub")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "subscribe":
                slug = message.get("tournament_slug")
                if slug:
                    await ws_manager.subscribe(websocket, slug)
                    await ws_manager.send_personal_message({"type": "subscribed", "slug": slug}, websocket)
            elif message.get("type") == "ping":
                await ws_manager.send_personal_message({"type": "pong"}, websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        print(f"Hub WS Error: {e}")
        ws_manager.disconnect(websocket)

@app.websocket("/ws/bot")
async def bot_websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect_bot(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "log":
                log_msg = message.get("message")
                log_level = message.get("level", "info")
                if log_msg:
                    from backend.core.database import add_bot_feed
                    await add_bot_feed(log_msg, log_level)
                    import datetime
                    await ws_manager.broadcast({
                        "type": "bot_feed_update",
                        "log": {
                            "message": log_msg,
                            "level": log_level,
                            "timestamp": datetime.datetime.now().isoformat()
                        }
                    })
            elif message.get("type") == "agent_response":
                resp_text = message.get("response")
                cmd_text = message.get("command")
                await ws_manager.broadcast({
                    "type": "agent_response",
                    "response": resp_text,
                    "command": cmd_text
                })
            elif message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect_bot()
    except Exception as e:
        print(f"Bot WS Error: {e}")
        ws_manager.disconnect_bot()

@app.websocket("/ws/overlay/{slot}")
async def overlay_websocket_endpoint(websocket: WebSocket, slot: str):
    await ws_manager.connect_overlay(websocket, slot)
    
    # Send initial state from DB
    from backend.core.database import get_overlays, get_stations
    stations = await get_stations()
    station = next((s for s in stations if s["id"] == slot), None)
    
    overlay_name = slot
    if station and station.get("active_overlay"):
        overlay_name = station["active_overlay"]
        
    overlays_list = await get_overlays()
    current = next((o for o in overlays_list if o["name"] == overlay_name), None)
    if current and current.get("config"):
        config = current["config"]
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except:
                pass
        if isinstance(config, dict):
            await websocket.send_text(json.dumps(config))
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "ping":
                await ws_manager.send_personal_message({"type": "pong"}, websocket)
            else:
                await ws_manager.broadcast_to_slot(slot, message)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        print(f"Overlay WS Error ({slot}): {e}")
        ws_manager.disconnect(websocket)

# Health check
@app.get("/health", tags=["system"], summary="Get API service health", operation_id="getHealth")
async def health_check():
    """Return backend server health verification indicator."""
    return {"status": "ok"}

# OBS Overlay endpoints
from fastapi.responses import RedirectResponse

@app.get("/obs/{station_id}", tags=["obs"], summary="Redirect to stream overlay viewer")
async def get_obs_overlay(station_id: str):
    """Redirect a browser or OBS browser source to the React stream overlay page for a given station."""
    return RedirectResponse(url=f"/obs?slot={station_id}")

@app.get("/obs/{station_id}/data", tags=["obs"], summary="Get stream overlay match telemetry")
async def get_obs_overlay_data(station_id: str):
    """Return the current active match telemetry data and overlay configuration for a given station."""
    from backend.core.database import get_active_matches, get_stations, get_overlays
    import json
    
    # 1. Fetch station details to find active overlay
    stations = await get_stations()
    station = next((s for s in stations if s["id"] == station_id), None)
    if not station:
        return {"elements": {}, "match": None}
        
    overlay_name = station.get("active_overlay") or station_id
    
    # 2. Fetch base overlay preset config
    overlays_list = await get_overlays()
    current_preset = next((o for o in overlays_list if o["name"] == overlay_name), None)
    
    base_config = {"elements": {}, "background_url": "", "global_font_url": "", "global_font_family": ""}
    if current_preset and current_preset.get("config"):
        config = current_preset["config"]
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except:
                pass
        if isinstance(config, dict):
            base_config = config
            
    # 3. Fetch active matches
    matches = await get_active_matches()
    active_match = next((m for m in matches if m["station_id"] == station_id and m["status"] in ["not_started", "called", "in_progress"]), None)
    
    return {
        "station": station,
        "overlay_name": overlay_name,
        "config": base_config,
        "active_match": active_match
    }

# Redirect root to docs or frontend
@app.get("/", tags=["system"], summary="Get root landing details", operation_id="getRoot")
async def root():
    """Return backend status greeting and landing description."""
    return {"message": "AI Tournament Organizer API is running. See /docs for API documentation."}


