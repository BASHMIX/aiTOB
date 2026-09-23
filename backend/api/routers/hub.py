from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any
from backend.core.database import (
    get_bot_feed, add_bot_feed, clear_bot_feed, add_hub_command, get_all_settings,
    get_setting, set_setting,
)
from backend.api.ws_manager import manager as hub_mgr
from backend.api.auth import verify_hub_password, require_global_settings_admin, require_permission
from backend.core.workspace_auth import SessionPrincipal
from backend.api.schemas import (
    BotCommandRequest, MessageResponse, ErrorResponse, BotFeedResponse,
    DispatcherMasterRequest,
)

router = APIRouter(tags=["hub"])

_auto_dispatcher_cache = None

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
    offset: int = Query(default=0, ge=0, description="Number of log feed entries to skip for pagination"),
    principal: SessionPrincipal | None = Depends(verify_hub_password),
):
    """Retrieve recently logged discord bot activities and execution events. Requires admin password authentication."""
    return BotFeedResponse(feed=await get_bot_feed(limit, offset, getattr(principal, "workspace_id", None)))


@router.delete(
    "/bot-feed",
    dependencies=[Depends(verify_hub_password)],
    summary="Clear bot feed",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="clearBotFeed"
)
async def api_clear_feed(principal: SessionPrincipal | None = Depends(verify_hub_password)):
    """Wipe all history entries from the internal discord bot feed database. Requires admin password authentication."""
    await clear_bot_feed(getattr(principal, "workspace_id", None))
    return MessageResponse(message="Feed cleared", ok=True)


@router.post(
    "/bot-command",
    dependencies=[Depends(verify_hub_password)],
    summary="Send a hub command to the bot",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="queueBotCommand"
)
async def api_bot_command(body: BotCommandRequest, principal: SessionPrincipal | None = Depends(verify_hub_password)):
    """Durably enqueue a workspace-scoped command for the managed Discord bot."""
    cmd = body.command
    if cmd:
        import datetime
        import json
        workspace_id = getattr(principal, "workspace_id", None)
        if not workspace_id:
            raise HTTPException(status_code=403, detail="A workspace session is required")
        await add_bot_feed(f"Admin command: {cmd}", "info", workspace_id)
        await hub_mgr.broadcast({"type": "bot_feed_update", "log": {
            "message": f"Admin command: {cmd}",
            "level": "info",
            "timestamp": datetime.datetime.now().isoformat()
        }, "_workspace_id": workspace_id})
        await add_hub_command(cmd, workspace_id=workspace_id)
        if hub_mgr.bot_connection:
            try:
                await hub_mgr.bot_connection.send_text(json.dumps({
                    "type": "drain",
                }))
            except Exception as e:
                print(f"Error nudging bot command queue: {e}")
        return MessageResponse(message="Command queued", ok=True)
    return MessageResponse(message="No command supplied", ok=False)


@router.post(
    "/hub/command",
    dependencies=[Depends(verify_hub_password)],
    summary="Execute a hub command",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="executeHubCommand"
)
async def api_hub_command(
    body: BotCommandRequest,
    principal: SessionPrincipal | None = Depends(require_permission("workspace.read")),
):
    """Legacy shim to the API-owned Assistant, never to the Discord bot.

    New clients use ``/ai/assistant/{tournament_slug}``.  Keeping this narrow
    compatibility path avoids a second Assistant execution route while making
    the tournament scope explicit.
    """
    import re
    from backend.core.ai_service import AIService, AIServiceError

    match = re.match(r"^\[Tournament:\s*([^\]]+)\]\s*(.+)$", body.command.strip(), re.S)
    if not match:
        raise HTTPException(400, "Use the tournament-scoped Organizer Assistant endpoint.")
    try:
        result = await AIService().answer(
            tournament_slug=match.group(1).strip(), question=match.group(2).strip(),
            workspace_id=getattr(principal, "workspace_id", None),
        )
    except AIServiceError as exc:
        raise HTTPException(409, str(exc)) from exc
    return MessageResponse(message=result["answer"], ok=True)



@router.get(
    "/status",
    dependencies=[Depends(require_global_settings_admin)],
    summary="Get service status",
    response_model=Dict[str, Any],
    responses={401: {"model": ErrorResponse}},
    operation_id="getServiceStatus"
)
async def api_get_status(principal: SessionPrincipal | None = Depends(require_global_settings_admin)):
    """Verify operational and connection statuses for database, websockets, and credentials scope. Requires admin password authentication."""
    from backend.core.integrations import configured_secret_types, list_integration_accounts
    workspace_id = getattr(principal, "workspace_id", None)
    startgg_connected = False
    if workspace_id:
        for account in await list_integration_accounts(workspace_id):
            if account.get("provider_type") != "startgg" or account.get("status") != "active":
                continue
            if "access_token" in await configured_secret_types(str(account["id"])):
                startgg_connected = True
                break

    global _auto_dispatcher_cache
    if _auto_dispatcher_cache is None:
        _auto_dispatcher_cache = (await get_setting("auto_dispatch_master_switch", "off") or "off").lower() == "on"
    dispatcher_on = _auto_dispatcher_cache

    # Check the Discord Bot state from the active WebSocket connection!
    from backend.api.ws_manager import manager as ws_manager
    bot_connected = ws_manager.bot_connection is not None

    return {
        "startgg_api": startgg_connected,
        "discord_bot": bot_connected,
        "websockets": True,
        "db": True,
        "token_scope": None,
        "auto_dispatcher": dispatcher_on,
    }


@router.post(
    "/workflows/reload",
    dependencies=[Depends(require_global_settings_admin)],
    summary="Hot-reload match transitions from docs/workflows.json",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    operation_id="reloadWorkflows"
)
async def api_reload_workflows(principal: SessionPrincipal | None = Depends(require_global_settings_admin)):
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
    workspace_id = getattr(principal, "workspace_id", None)
    await add_bot_feed(f"♻️ Match-workflow transitions reloaded ({state_count} states)", "info", workspace_id)
    await hub_mgr.broadcast({"type": "status_update", "_workspace_id": workspace_id})
    return MessageResponse(message=f"Reloaded {state_count} states", ok=True)


@router.post(
    "/dispatcher/master",
    dependencies=[Depends(require_global_settings_admin)],
    summary="Flip the GLOBAL auto-dispatcher kill switch",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    operation_id="setDispatcherMaster"
)
async def api_set_dispatcher_master(
    body: DispatcherMasterRequest,
    principal: SessionPrincipal | None = Depends(require_global_settings_admin),
):
    """Master ON/OFF for the auto-dispatcher across all tournaments.

    When OFF, no tournament's `auto_dispatch_enabled` setting has any effect —
    every match must be called manually. This is the panic button: flipping
    OFF takes effect within ~20 seconds (next dispatcher tick) and leaves
    any already-dispatched matches running normally. Flipping back ON also
    clears one-shot "Top-8 reached" notifications so they fire again if needed.
    """
    new_state = "on" if body.enabled else "off"
    await set_setting("auto_dispatch_master_switch", new_state)
    global _auto_dispatcher_cache
    _auto_dispatcher_cache = new_state == "on"
    # Clear stop-signaled flags so re-enabling re-emits Top-N notices if applicable.
    # Keys are now per-event (_dispatcher_stop_signaled_{slug}_{event_id}), so wipe
    # the whole family in one prefix delete.
    if body.enabled:
        from backend.core.database import clear_settings_prefix
        await clear_settings_prefix("_dispatcher_stop_signaled_")
    else:
        from backend.core.database import cancel_pending_dispatcher_work
        cancelled = await cancel_pending_dispatcher_work()
        if cancelled:
            await add_bot_feed(
                f"🤖 Auto-dispatcher cancelled {cancelled} pending automatic item(s).",
                "warn",
            )
    await add_bot_feed(
        f"🤖 Auto-dispatcher master switch: {new_state.upper()}",
        "warn" if not body.enabled else "info"
    )
    await hub_mgr.broadcast({"type": "status_update"})
    return MessageResponse(message=f"Dispatcher {new_state}", ok=True)
