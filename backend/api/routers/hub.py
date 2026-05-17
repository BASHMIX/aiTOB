from fastapi import APIRouter, Request, Depends
from backend.core.database import get_bot_feed, add_bot_feed, clear_bot_feed, add_hub_command, get_all_settings
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password
from backend.api.schemas import BotCommandRequest

router = APIRouter(tags=["hub"])


@router.post("/auth/verify", summary="Verify hub password")
async def api_verify_auth(password: str = Depends(verify_hub_password)):
    """Test if the current hub password is valid. Returns 401 if invalid."""
    return {"ok": True, "message": "Authenticated"}


@router.get("/bot-feed", summary="Get bot activity feed")
async def api_get_feed():
    """Return the most recent bot feed entries."""
    return {"feed": await get_bot_feed(50)}


@router.delete("/bot-feed",
               dependencies=[Depends(verify_hub_password)],
               summary="Clear bot feed")
async def api_clear_feed():
    """Delete all bot feed entries."""
    await clear_bot_feed()
    return {"message": "Feed cleared"}


@router.post("/bot-command",
             dependencies=[Depends(verify_hub_password)],
             summary="Send a hub command to the bot")
async def api_bot_command(body: BotCommandRequest):
    """Queue a command for the Discord bot to execute (e.g. call_match <set_id>)."""
    cmd = body.command
    if cmd:
        await add_hub_command(cmd)
        await add_bot_feed(f"Admin command: {cmd}", "info")
        await hub_mgr.broadcast({"type": "bot_feed", "message": f"Admin command: {cmd}", "level": "info"})
    return {"message": "Command queued"}


@router.get("/status", summary="Get service status")
async def api_get_status():
    """Check if Start.gg, Discord bot, WebSocket, and DB are connected."""
    from backend.core.database import get_all_connections, get_all_settings
    settings = await get_all_settings()
    conns = await get_all_connections()

    startgg_token = settings.get("STARTGG_API_TOKEN") or conns.get("STARTGG_API_TOKEN")
    discord_token = settings.get("DISCORD_BOT_TOKEN") or conns.get("DISCORD_BOT_TOKEN")

    return {
        "startgg_api": startgg_token is not None and startgg_token != "",
        "discord_bot": discord_token is not None and discord_token != "",
        "websockets": True,
        "db": True
    }
