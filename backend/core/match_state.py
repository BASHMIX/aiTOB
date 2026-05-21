import asyncio
import random
import datetime
from backend.core.startgg_client import get_client
from backend.core.database import get_active_match, upsert_active_match, update_active_match, add_bot_feed
from backend.api.ws_manager import manager as hub_mgr

import json
import os

VALID_TRANSITIONS = {
    "not_started": ["called"],
    "called":       ["in_progress", "complete", "not_started"],
    "in_progress":  ["complete", "conflict", "not_started"],
    "conflict":     ["complete", "not_started"],
    "complete":     ["not_started"],
}

def load_workflow_transitions():
    global VALID_TRANSITIONS
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        json_path = os.path.join(root_dir, "docs", "workflows.json")
        
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                match_workflow = data.get("match_workflow", {})
                states = match_workflow.get("states", {})
                
                new_transitions = {}
                for state, config in states.items():
                    new_transitions[state] = config.get("allowed_next", [])
                
                if new_transitions:
                    VALID_TRANSITIONS = new_transitions
    except Exception as e:
        print(f"Warning: Failed to load workflow configuration from docs/workflows.json: {e}")

# Initial load
load_workflow_transitions()

def validate_transition(from_status: str, to_status: str) -> bool:
    allowed = VALID_TRANSITIONS.get(from_status, [])
    return to_status in allowed

def generate_lobby_password() -> str:
    return str(random.randint(1000, 9999))

async def transition_match(set_id: str, to_status: str, **kwargs) -> dict:
    match = await get_active_match(set_id)
    if not match:
        return {"error": "Match not found"}

    current = match.get("status", "not_started")
    if not validate_transition(current, to_status):
        return {"error": f"Cannot transition from {current} to {to_status}"}

    update_kwargs = {"status": to_status, **kwargs}

    if to_status == "called":
        now = datetime.datetime.utcnow().isoformat()
        update_kwargs["called_at"] = now
        update_kwargs["p1_ready"] = False
        update_kwargs["p2_ready"] = False

    elif to_status == "in_progress":
        update_kwargs["started_at"] = datetime.datetime.utcnow().isoformat()
        if match.get("bot_enabled", True):
            from backend.core.database import add_hub_command
            await add_hub_command(f"dm_score_request {set_id}")

    elif to_status == "not_started":
        update_kwargs["p1_score"] = 0
        update_kwargs["p2_score"] = 0
        update_kwargs["p1_ready"] = False
        update_kwargs["p2_ready"] = False
        update_kwargs["called_at"] = None
        update_kwargs["started_at"] = None
        update_kwargs["dq_player"] = None
        update_kwargs["lobby_password"] = None

    await upsert_active_match(set_id, **update_kwargs)
    await hub_mgr.broadcast({"type": "match_update"})
    return {"ok": True, "status": to_status}

async def auto_dq_match(set_id: str) -> dict:
    match = await get_active_match(set_id)
    if not match:
        return {"error": "Match not found"}

    p1_ready = match.get("p1_ready")
    p2_ready = match.get("p2_ready")
    sgg = get_client()

    if not p1_ready and p2_ready:
        dq_eid = match.get("p1_entrant_id")
        winner_eid = match.get("p2_entrant_id")
    elif p1_ready and not p2_ready:
        dq_eid = match.get("p2_entrant_id")
        winner_eid = match.get("p1_entrant_id")
    else:
        dq_eid = None
        winner_eid = None

    if winner_eid:
        try:
            await sgg.mark_set_dq(set_id, winner_eid)
        except Exception as e:
            await add_bot_feed(f"Start.gg auto-DQ failed for match {set_id}: {e}", "error")

    await update_active_match(set_id, status="complete", dq_player=dq_eid)
    await hub_mgr.broadcast({"type": "match_update"})
    return {"ok": True, "dq_player": dq_eid}

async def start_call_timer(set_id: str, timeout_seconds: int = 600):
    await asyncio.sleep(timeout_seconds)
    match = await get_active_match(set_id)
    if match and match.get("status") == "called":
        await add_bot_feed(f"⏰ Call timer expired for match {set_id}, auto-DQ triggered", "warn")
        await auto_dq_match(set_id)
