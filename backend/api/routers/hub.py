from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any
from backend.core.database import (
    get_bot_feed, add_bot_feed, clear_bot_feed, add_hub_command, get_all_settings,
    get_setting, set_setting,
)
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password
from backend.api.schemas import (
    BotCommandRequest, MessageResponse, ErrorResponse, BotFeedResponse,
    DispatcherMasterRequest,
)

router = APIRouter(tags=["hub"])


@router.post(
    "/auth/verify",
    summary="Verify hub password",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="verifyHubPassword"
)
async def api_verify_auth(password: str = Depends(verify_hub_password)):
    """Verify if the provided administrator hub password is correct. Returns 401 if unauthorized."""
    return MessageResponse(message="Authenticated", ok=True)


@router.get(
    "/bot-feed",
    dependencies=[Depends(verify_hub_password)],
    summary="Get bot activity feed",
    response_model=BotFeedResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="getBotFeed"
)
async def api_get_feed(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of log feed entries to fetch"),
    offset: int = Query(default=0, ge=0, description="Number of log feed entries to skip for pagination")
):
    """Retrieve recently logged discord bot activities and execution events. Requires admin password authentication."""
    return BotFeedResponse(feed=await get_bot_feed(limit, offset))


@router.delete(
    "/bot-feed",
    dependencies=[Depends(verify_hub_password)],
    summary="Clear bot feed",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="clearBotFeed"
)
async def api_clear_feed():
    """Wipe all history entries from the internal discord bot feed database. Requires admin password authentication."""
    await clear_bot_feed()
    return MessageResponse(message="Feed cleared", ok=True)


@router.post(
    "/bot-command",
    dependencies=[Depends(verify_hub_password)],
    summary="Send a hub command to the bot",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="queueBotCommand"
)
async def api_bot_command(body: BotCommandRequest):
    """Enqueue a text command to be processed by the background Discord bot client. Requires admin password authentication."""
    cmd = body.command
    if cmd:
        import datetime
        import json
        await add_bot_feed(f"Admin command: {cmd}", "info")
        await hub_mgr.broadcast({"type": "bot_feed_update", "log": {
            "message": f"Admin command: {cmd}",
            "level": "info",
            "timestamp": datetime.datetime.now().isoformat()
        }})
        if hub_mgr.bot_connection:
            try:
                await hub_mgr.bot_connection.send_text(json.dumps({
                    "type": "command",
                    "command": cmd
                }))
                return MessageResponse(message="Command sent to bot", ok=True)
            except Exception as e:
                print(f"Error sending command to bot WS: {e}")
        await add_hub_command(cmd)
    return MessageResponse(message="Command queued (Bot offline)", ok=True)


@router.post(
    "/hub/command",
    dependencies=[Depends(verify_hub_password)],
    summary="Execute a hub command",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="executeHubCommand"
)
async def api_hub_command(body: BotCommandRequest):
    """Execute an administrative command via natural language or structured commands.
    
    Routes the command to the bot WebSocket, which processes it asynchronously.
    """
    cmd = body.command
    if cmd:
        import datetime
        import json
        await add_bot_feed(f"Admin command: {cmd}", "info")
        await hub_mgr.broadcast({"type": "bot_feed_update", "log": {
            "message": f"Admin command: {cmd}",
            "level": "info",
            "timestamp": datetime.datetime.now().isoformat()
        }})
        if hub_mgr.bot_connection:
            try:
                await hub_mgr.bot_connection.send_text(json.dumps({
                    "type": "command",
                    "command": cmd
                }))
                return MessageResponse(message="Command sent to bot", ok=True)
            except Exception as e:
                print(f"Error sending command to bot WS: {e}")
        await add_hub_command(cmd)
    return MessageResponse(message="Command queued (Bot offline)", ok=True)



@router.get(
    "/status",
    dependencies=[Depends(verify_hub_password)],
    summary="Get service status",
    response_model=Dict[str, Any],
    responses={401: {"model": ErrorResponse}},
    operation_id="getServiceStatus"
)
async def api_get_status():
    """Verify operational and connection statuses for database, websockets, and credentials scope. Requires admin password authentication."""
    from backend.core.database import get_all_connections, get_all_settings
    import json
    settings = await get_all_settings()
    conns = await get_all_connections()

    startgg_token = settings.get("STARTGG_API_TOKEN") or conns.get("STARTGG_API_TOKEN")
    discord_token = settings.get("DISCORD_BOT_TOKEN") or conns.get("DISCORD_BOT_TOKEN")

    token_scope_status = settings.get("token_scope_status")
    token_scope = None
    if token_scope_status:
        try:
            token_scope = json.loads(token_scope_status)
        except Exception:
            pass

    dispatcher_on = (await get_setting("auto_dispatch_master_switch", "off") or "off").lower() == "on"

    # Check the Discord Bot state from the active WebSocket connection!
    from backend.api.ws_manager import manager as ws_manager
    bot_connected = ws_manager.bot_connection is not None

    return {
        "startgg_api": startgg_token is not None and startgg_token != "",
        "discord_bot": bot_connected,
        "websockets": True,
        "db": True,
        "token_scope": token_scope,
        "auto_dispatcher": dispatcher_on,
    }


@router.post(
    "/workflows/reload",
    dependencies=[Depends(verify_hub_password)],
    summary="Hot-reload match transitions from docs/workflows.json",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    operation_id="reloadWorkflows"
)
async def api_reload_workflows():
    """Re-read docs/workflows.json without restarting the API.

    Use during a live event when you need to adjust allowed state transitions
    (e.g., add a 'paused' state, allow conflict→in_progress) without taking
    the hub down. The change takes effect immediately for all subsequent
    transition_match() calls. Existing matches in valid states are unaffected.
    """
    from backend.core.match_state import load_workflow_transitions, VALID_TRANSITIONS
    try:
        load_workflow_transitions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload failed: {e}")
    state_count = len(VALID_TRANSITIONS)
    await add_bot_feed(f"♻️ Match-workflow transitions reloaded ({state_count} states)", "info")
    await hub_mgr.broadcast({"type": "status_update"})
    return MessageResponse(message=f"Reloaded {state_count} states", ok=True)


@router.post(
    "/dispatcher/master",
    dependencies=[Depends(verify_hub_password)],
    summary="Flip the GLOBAL auto-dispatcher kill switch",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="setDispatcherMaster"
)
async def api_set_dispatcher_master(body: DispatcherMasterRequest):
    """Master ON/OFF for the auto-dispatcher across all tournaments.

    When OFF, no tournament's `auto_dispatch_enabled` setting has any effect —
    every match must be called manually. This is the panic button: flipping
    OFF takes effect within ~20 seconds (next dispatcher tick) and leaves
    any already-dispatched matches running normally. Flipping back ON also
    clears one-shot "Top-8 reached" notifications so they fire again if needed.
    """
    new_state = "on" if body.enabled else "off"
    await set_setting("auto_dispatch_master_switch", new_state)
    # Clear stop-signaled flags so re-enabling re-emits Top-N notices if applicable.
    if body.enabled:
        from backend.core.database import get_tournaments
        for t in await get_tournaments():
            await set_setting(f"_dispatcher_stop_signaled_{t['slug']}", "")
    await add_bot_feed(
        f"🤖 Auto-dispatcher master switch: {new_state.upper()}",
        "warn" if not body.enabled else "info"
    )
    await hub_mgr.broadcast({"type": "status_update"})
    return MessageResponse(message=f"Dispatcher {new_state}", ok=True)
