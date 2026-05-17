import os, json
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import init_db, get_setting, set_setting
from backend.api.ws_manager import manager as ws_manager
from backend.api.routers.players import router as players_router
from backend.api.routers.matches import router as matches_router
from backend.api.routers.tournaments import router as tournaments_router
from backend.api.routers.overlays import router as overlays_router
from backend.api.routers.settings import router as settings_router
from backend.api.routers.hub import router as hub_router
from backend.api.routers.stations import router as stations_router
from backend.api.routers.assets import router as assets_router

load_dotenv()

app = FastAPI(title="AI Tournament Organizer API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers — prefixes must match what the frontend calls
app.include_router(tournaments_router, prefix="/api/tournaments")
app.include_router(players_router,     prefix="/api/players")
app.include_router(stations_router,    prefix="/api/stations")
app.include_router(overlays_router,    prefix="/api/overlays")
app.include_router(assets_router,      prefix="/api/assets")
# These routers define their own sub-paths (/settings, /env, /bot-feed, /active-matches…)
app.include_router(settings_router,    prefix="/api")
app.include_router(hub_router,         prefix="/api")
app.include_router(matches_router,     prefix="/api")

# Static files
BASE_DIR = os.path.dirname(__file__)
static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Startup
@app.on_event("startup")
async def startup_event():
    await init_db()
    # Migration of env to DB
    important_vars = ["STARTGG_API_TOKEN", "DISCORD_BOT_TOKEN", "GOOGLE_API_KEY", "HUB_PASSWORD"]
    for v in important_vars:
        db_val = await get_setting(v)
        env_val = os.getenv(v)
        if not db_val and env_val:
            await set_setting(v, env_val)
    print("[SYS] API Started and Config Migrated")

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

@app.websocket("/ws/overlay/{slot}")
async def overlay_websocket_endpoint(websocket: WebSocket, slot: str):
    await ws_manager.connect_overlay(websocket, slot)
    
    # Send initial state from DB
    from backend.core.database import get_overlays
    overlays_list = await get_overlays()
    current = next((o for o in overlays_list if o["name"] == slot), None)
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
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Redirect root to docs or frontend
@app.get("/")
async def root():
    return {"message": "AI Tournament Organizer API is running. See /docs for API documentation."}
