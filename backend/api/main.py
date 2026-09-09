import os, json
import logging
import asyncio
from fastapi import FastAPI, Header, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import init_db, get_setting, get_all_settings, set_setting
from backend.core.storage import require_runtime_database
from backend.api.ws_manager import manager as ws_manager
from backend.api.routers.players import router as players_router
from backend.api.routers.matches import router as matches_router
from backend.api.routers.tournaments import router as tournaments_router
from backend.api.routers.overlays import router as overlays_router
from backend.api.routers.settings import router as settings_router
from backend.api.routers.integrations import router as integrations_router
from backend.api.routers.hub import router as hub_router
from backend.api.routers.stations import router as stations_router
from backend.api.routers.assets import router as assets_router
from backend.api.routers.auth import router as auth_router
from backend.api.routers.planned_streams import router as planned_streams_router
from backend.api.routers.providers import router as providers_router
from backend.api.routers.challonge_oauth import router as challonge_oauth_router
from backend.api.routers.action_proposals import router as action_proposals_router
from backend.api.routers.organizer_console import router as organizer_console_router
from backend.api.routers.ai_service import router as ai_service_router
from backend.api.routers.session import router as session_router

load_dotenv()
logger = logging.getLogger("aitob.api")
_background_tasks: set[asyncio.Task] = set()


def _start_background(coroutine):
    task = asyncio.create_task(coroutine)
    _background_tasks.add(task)
    def finished(done):
        _background_tasks.discard(done)
        if not done.cancelled() and done.exception() is not None:
            logger.error("API background task failed; inspect service health")
    task.add_done_callback(finished)
    return task

app = FastAPI(
    title="FNC Tournament Organizer API",
    description=(
        "AI-powered match coordination, registration, and overlay management system. "
        "Integrates Discord bot automations with Start.gg bracket management APIs."
    ),
    version="1.0.0",
    servers=[{"url": "http://localhost:8000", "description": "Development Server"}]
)

# CORS — allowed origins are environment-driven so the same code path serves
# local dev and the public deployment.
#   • Production: set ALLOWED_ORIGINS in .env as a comma-separated list, e.g.
#     ALLOWED_ORIGINS=https://hub.mydomain.com,https://overlays.mydomain.com
#   • Local dev (var unset/empty): fall back to Vite + local uvicorn origins.
DEV_ORIGINS = [
    "http://localhost:5173",   # Vite dev server (frontend-react)
    "http://127.0.0.1:5173",
    "http://localhost:8000",   # uvicorn — same-host OBS browser sources / hub.html
    "http://127.0.0.1:8000",
]

_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or DEV_ORIGINS
if os.getenv("AITOB_ENV", "development").lower() == "production" and not _origins_env:
    raise RuntimeError("ALLOWED_ORIGINS is required when AITOB_ENV=production")

# Optional: allow a whole subdomain space for cloud-hosted overlays (set only if needed),
# e.g. ALLOWED_ORIGIN_REGEX=https://.*\.mydomain\.com
_origin_regex = os.getenv("ALLOWED_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def session_csrf_guard(request: Request, call_next):
    """Reject cross-origin cookie mutations while preserving bearer clients."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.cookies.get("aitob_session"):
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        candidate = origin or (referer.rstrip("/") if referer else None)
        if candidate and not any(candidate == allowed or candidate.startswith(allowed + "/") for allowed in allowed_origins):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"error": True, "message": "Cross-origin request rejected"})
    return await call_next(request)

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
    # Do not reflect provider responses, credentials, or local paths to a
    # browser.  Operators correlate the redacted server event by request path.
    logger.error("Unhandled API exception on %s (%s)", request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "Internal Server Error"}
    )

# Routers — prefixes must match what the frontend calls
app.include_router(tournaments_router, prefix="/api/tournaments")
app.include_router(players_router,     prefix="/api/players")
app.include_router(stations_router,    prefix="/api/stations")
app.include_router(overlays_router,    prefix="/api/overlays")
app.include_router(assets_router,      prefix="/api/assets")
app.include_router(auth_router,        prefix="/api/auth")
app.include_router(session_router,     prefix="/api")
# These routers define their own sub-paths (/settings, /env, /bot-feed, /active-matches…)
app.include_router(settings_router,    prefix="/api")
app.include_router(integrations_router, prefix="/api")
app.include_router(hub_router,         prefix="/api")
app.include_router(matches_router,     prefix="/api")
app.include_router(planned_streams_router, prefix="/api")
app.include_router(providers_router, prefix="/api/providers")
app.include_router(challonge_oauth_router, prefix="/api/auth")
app.include_router(action_proposals_router, prefix="/api")
app.include_router(organizer_console_router, prefix="/api")
app.include_router(ai_service_router, prefix="/api")


# Static files
BASE_DIR = os.path.dirname(__file__)
static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Serve frontend assets in production if dist folder exists
frontend_assets_dir = os.path.join(static_dir, "dist", "assets")
if os.path.exists(frontend_assets_dir):
    app.mount("/assets", StaticFiles(directory=frontend_assets_dir), name="frontend_assets")

# Background Tasks & Helper Loops
_CHALLONGE_TERMINAL_STATES = {"complete", "completed", "awaiting_review", "finalized"}
_recovery_service = None

def is_completed_challonge_snapshot(tournament: dict) -> bool:
    """Avoid spending API quota polling a bracket already known to be final."""
    if tournament.get("provider_type") != "challonge":
        return False
    try:
        raw = json.loads(tournament.get("raw_data") or "{}")
    except (TypeError, json.JSONDecodeError):
        return False
    return str(raw.get("provider_state") or "").lower() in _CHALLONGE_TERMINAL_STATES

async def sync_tracked_tournaments() -> None:
    """Refresh every saved bracket once; failures are visible and never silently
    treated as fresh local data. Used before the periodic loop is released."""
    from backend.core.database import get_tournaments, set_tournament_sync_status
    from backend.core.provider_sync_manager import sync_manager
    from backend.api.ws_manager import manager as hub_mgr
    for tournament in await get_tournaments():
        slug = tournament.get("slug")
        if not slug: continue
        if is_completed_challonge_snapshot(tournament):
            continue
        try:
            # Challonge startup reads are exclusively issued by the Live
            # scheduler (or an explicit manual/stale-open trigger). This avoids
            # a duplicate startup read racing the first Live cycle.
            if tournament.get("provider_type") == "challonge":
                continue
            await sync_manager.sync_bracket(
                slug,
                workspace_id=tournament.get("workspace_id"),
                reason="startup",
            )
        except Exception as exc:
            await set_tournament_sync_status(slug, False, str(exc))
            print(f"[SYS] Initial sync failed for {slug}: {exc}")
    # Emit only to the owning workspace; the broadcast manager drops any
    # unscoped event rather than risking cross-tenant data.
    for tournament in await get_tournaments():
        if tournament.get("workspace_id"):
            await hub_mgr.broadcast({"type": "match_update", "_workspace_id": tournament["workspace_id"]})

async def reconciliation_loop():
    """Background task that periodically (every 45s) keeps local active_matches in sync with Start.gg."""
    import asyncio
    from backend.core.database import get_tournaments, set_tournament_sync_status
    from backend.core.provider_sync_manager import sync_manager
    from backend.api.ws_manager import manager as hub_mgr

    print("[SYS] Tournament reconciliation background task started")
    while True:
        try:
            await asyncio.sleep(45)
            tournaments = await get_tournaments()
            for t in tournaments:
                slug = t.get("slug")
                if not slug:
                    continue
                if is_completed_challonge_snapshot(t):
                    continue
                if t.get("provider_type") == "challonge":
                    # Challonge is exclusively owned by LiveSyncScheduler.
                    # Economy creates no polling task, and Live has exactly one
                    # scheduler per tournament, preventing overlapping reads.
                    continue
                try:
                    await sync_manager.sync_bracket(
                        slug,
                        workspace_id=t.get("workspace_id"),
                        reason="periodic",
                    )
                    # Broadcast updates to hub clients
                    await hub_mgr.broadcast({"type": "match_update", "_workspace_id": t.get("workspace_id")})
                except Exception as e:
                    await set_tournament_sync_status(slug, False, str(e))
                    print(f"[SYS] Reconciliation failed for tournament {slug}: {e}")
        except asyncio.CancelledError:
            print("[SYS] Start.gg reconciliation background task cancelled")
            break
        except Exception as e:
            print(f"[SYS] Error in reconciliation loop: {e}")

# Startup
async def _send_drain_to_bot():
    """Push an event-driven drain nudge to the bot over its WebSocket so it
    executes a just-queued hub command immediately (no polling). No-op when the
    bot is offline — the row stays in the queue for the bot's 60s fallback sweep."""
    if ws_manager.bot_connection:
        try:
            await ws_manager.bot_connection.send_text(json.dumps({"type": "drain"}))
        except Exception as e:
            print(f"[API] drain nudge to bot failed: {e}")


def _notify_bot_drain():
    """Sync listener fired by add_hub_command (API process) — schedule the nudge."""
    try:
        asyncio.get_running_loop()
        _start_background(_send_drain_to_bot())
    except RuntimeError:
        pass  # no running loop (shouldn't happen inside a request)


@app.on_event("startup")
async def startup_event():
    import asyncio
    # Fail before migrations, workers, polling, or an external command can
    # begin. Runtime never falls back to the legacy SQLite file.
    require_runtime_database()
    await init_db()
    # Wire the event-driven hub-command outbox: when the API enqueues a command,
    # immediately nudge the bot to drain it instead of waiting on a poll.
    from backend.core.database import set_hub_command_listener
    set_hub_command_listener(_notify_bot_drain)
    # Credential migration is an explicit, audited operation, not a startup
    # side effect that can recreate plaintext after secure migration.
    print("[SYS] API Started")

    # Restore only Hub-local workflow from SQLite. This creates no provider
    # mutation and does not auto-DQ an attendance deadline that elapsed while
    # aiTOB was offline.
    from backend.core.provider_feature_flags import get_provider_feature_flags
    global _recovery_service
    flags = get_provider_feature_flags()
    if flags.challonge_local_workflow_enabled:
        from backend.core.recovery import RecoveryService
        _recovery_service = RecoveryService()
        report = await _recovery_service.restore()
        print(f"[SYS] Restored {len(report.restored_matches)} local workflow match(es)")
    # Live remains opt-in per tournament. Economy mode starts no polling task.
    if flags.challonge_read_enabled:
        from backend.core.provider_sync_manager import sync_manager
        await sync_manager.restore_live_schedules()

    # Run token permission probe on startup in background
    async def run_token_probe():
        try:
            from backend.core.providers.startgg.client import get_client
            client = get_client()
            client.token = None # Force reload from settings/DB
            probe_result = await client.probe_token_permissions()
            await set_setting("token_scope_status", json.dumps(probe_result))
            print("[SYS] Start.gg token probe complete")
        except Exception:
            print("[SYS] Startup Start.gg token probe failed")
    
    _start_background(run_token_probe())

    # A fresh snapshot is required before bot/admin workflows consume saved sets.
    await sync_tracked_tournaments()
    # Start the periodic reconciliation loop in background
    _start_background(reconciliation_loop())


@app.on_event("shutdown")
async def shutdown_event():
    global _recovery_service
    from backend.core.database import set_hub_command_listener
    set_hub_command_listener(None)
    tasks = tuple(_background_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _background_tasks.clear()
    if _recovery_service:
        await _recovery_service.close()
        _recovery_service = None
    from backend.core.provider_sync_manager import sync_manager
    await sync_manager.close_live_schedules()


# WebSocket Endpoint
@app.websocket("/ws/hub")
async def websocket_endpoint(websocket: WebSocket):
    from backend.core.workspace_auth import SESSION_COOKIE, get_session_principal
    principal = await get_session_principal(websocket.cookies.get(SESSION_COOKIE))
    if not principal:
        await websocket.close(code=4401)
        return
    await ws_manager.connect(websocket, principal.workspace_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "subscribe":
                slug = message.get("tournament_slug")
                from backend.core.database import get_tournament
                if slug and await get_tournament(slug, principal.workspace_id):
                    await ws_manager.subscribe(websocket, principal.workspace_id, slug)
                    await ws_manager.send_personal_message({"type": "subscribed", "slug": slug}, websocket)
                elif slug:
                    await ws_manager.send_personal_message({"type": "subscription_denied"}, websocket)
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
    await websocket.accept()
    try:
        auth_message = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=10))
        from backend.core.overlay_access import resolve_overlay_access
        access = await resolve_overlay_access(str(auth_message.get("token") or ""), slot)
        if auth_message.get("type") != "authenticate" or not access:
            await websocket.close(code=4401)
            return
        ws_manager.register_overlay(websocket, slot, access["workspace_id"])
        await websocket.send_text(json.dumps({"type": "authenticated"}))
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "ping":
                await ws_manager.send_personal_message({"type": "pong"}, websocket)
            else:
                await ws_manager.broadcast_to_slot(slot, message, access["workspace_id"])
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


@app.get("/readiness", tags=["system"], summary="Verify runtime database readiness", operation_id="getReadiness")
async def readiness_check():
    """A redacted internal readiness signal: no DSN/provider credentials leak."""
    try:
        require_runtime_database()
        from backend.core.database import aiosqlite, DB_PATH
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("SELECT 1")
        return {"status": "ready", "database": "postgresql"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})

# OBS Overlay endpoints
from fastapi.responses import RedirectResponse

@app.get("/obs/{station_id}", tags=["obs"], summary="Redirect to stream overlay viewer")
async def get_obs_overlay(station_id: str):
    """Redirect a browser or OBS browser source to the React stream overlay page for a given station."""
    return RedirectResponse(url=f"/obs?slot={station_id}")

@app.get("/obs/{station_id}/data", tags=["obs"], summary="Get stream overlay match telemetry")
async def get_obs_overlay_data(station_id: str, x_overlay_token: str | None = Header(default=None)):
    """Return the current active match telemetry data and overlay configuration for a given station."""
    from backend.core.database import get_active_matches, get_station, get_overlays
    from backend.core.overlay_access import resolve_overlay_access
    import json
    
    # 1. Fetch station details to find active overlay
    access = await resolve_overlay_access(x_overlay_token or "", station_id)
    if not access:
        raise HTTPException(status_code=401, detail="Overlay link is invalid or revoked")
    workspace_id = access["workspace_id"]
    station = await get_station(station_id, workspace_id)
    if not station:
        raise HTTPException(status_code=404, detail="Overlay station not found")
        
    overlay_name = station.get("active_overlay") or station_id
    
    # 2. Fetch base overlay preset config
    overlays_list = await get_overlays(workspace_id)
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
    matches = await get_active_matches(workspace_id=workspace_id)
    active_match = next((m for m in matches if m["station_id"] in {station_id, station["storage_id"]} and m["status"] in ["not_started", "called", "in_progress"]), None)
    tournament_name = None
    if active_match and active_match.get("tournament_slug"):
        from backend.core.database import get_tournament
        tournament = await get_tournament(active_match["tournament_slug"], workspace_id)
        tournament_name = (tournament or {}).get("name")
    
    return {
        "station": station,
        "overlay_name": overlay_name,
        "config": base_config,
        "active_match": active_match
        ,"tournament_name": tournament_name
    }

# Redirect root to docs or frontend
@app.get("/", tags=["system"], summary="Get root landing details", operation_id="getRoot")
async def root():
    """Return backend status greeting or serve production React index.html."""
    index_file = os.path.join(static_dir, "dist", "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "AI Tournament Organizer API is running. See /docs for API documentation."}


@app.get("/{catchall:path}", tags=["system"], summary="Serve frontend client-side routes")
async def serve_frontend(catchall: str):
    """Fallback handler to support HTML5 History mode in React Router."""
    # Exclude API, Static, and WebSocket paths from being caught by SPA router
    if catchall.startswith("api") or catchall.startswith("static") or catchall.startswith("ws"):
        raise HTTPException(status_code=404, detail="Not Found")
    
    index_file = os.path.join(static_dir, "dist", "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Not Found")


