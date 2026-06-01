import asyncio
import random
import datetime
from backend.core.providers.registry import get_provider_for_tournament
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
                    # Overlay states (e.g. on_stream) are derived views for docs/UI only —
                    # not real transition nodes, so keep them out of VALID_TRANSITIONS.
                    if config.get("overlay"):
                        continue
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
        # Push state to provider so start.gg viewers see "currently playing"
        # instead of staying in CALLED until the score report lands. Best-effort
        # — failures here are non-critical (the score report will mark in_progress
        # again as a pre-step) but logged so divergence is visible.
        try:
            provider = await get_provider_for_tournament(match.get("tournament_slug") or "")
            result = await provider.mark_in_progress(set_id)
            if not result.success:
                await add_bot_feed(
                    f"⚠️ markSetInProgress failed for {set_id}: {result.error_message}", "warn"
                )
        except Exception as e:
            await add_bot_feed(f"⚠️ markSetInProgress error for {set_id}: {e}", "warn")

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

    # Hard guard: if a TO/player flipped the disarm flag (partial-reach matches,
    # off-Discord coordination) we must NOT issue a DQ regardless of who pressed Ready.
    if match.get("auto_dq_disarmed"):
        await add_bot_feed(
            f"auto_dq_match called for {set_id} but match is disarmed — skipping mutation", "warn"
        )
        return {"ok": False, "skipped": "disarmed"}

    provider = await get_provider_for_tournament(match.get("tournament_slug") or "")

    # Race guard: if start.gg already shows COMPLETED (players self-reported on the
    # web UI while we were waiting), do NOT call mark_dq — it would overwrite a real
    # result with a DQ flag. Sync local state instead.
    try:
        sgg_state = await provider.fetch_set_state(set_id)
    except Exception:
        sgg_state = None
    # SGG_STATE_MAP: 3 == COMPLETE on start.gg. We import via the enum to stay provider-agnostic.
    from backend.core.contracts.tournament_types import ProviderSetState
    if sgg_state == ProviderSetState.COMPLETE:
        await add_bot_feed(
            f"auto_dq_match skipped for {set_id}: start.gg already shows COMPLETED. Syncing local state instead.",
            "info"
        )
        await update_active_match(set_id, status="complete", dq_player=None)
        await hub_mgr.broadcast({"type": "match_update"})
        return {"ok": True, "synced_from_provider": True}

    p1_ready = match.get("p1_ready")
    p2_ready = match.get("p2_ready")
    p1_eid = match.get("p1_entrant_id")
    p2_eid = match.get("p2_entrant_id")

    if not p1_ready and p2_ready:
        dq_eid = p1_eid
        winner_eid = p2_eid
    elif p1_ready and not p2_ready:
        dq_eid = p2_eid
        winner_eid = p1_eid
    else:
        # Double no-show — neither (or, defensively, both) checked in. DQ BOTH.
        dq_eid = "both"
        winner_eid = None

    # Validate the local move BEFORE touching the provider so we never fire a
    # mutation we'd then refuse to record locally (e.g. an already-complete set).
    current = match.get("status", "not_started")
    if not validate_transition(current, "complete"):
        await add_bot_feed(f"auto-DQ blocked: cannot transition {current} → complete for {set_id}", "warn")
        return {"error": True, "message": f"Invalid transition from {current}"}

    if dq_eid == "both":
        # Resolve the set on the provider so the bracket doesn't stall. start.gg
        # can't DQ both slots in one call — it advances one as a technical winner —
        # so warn the TO to verify the advanced slot upstream.
        if p1_eid and p2_eid:
            result = await provider.mark_double_dq(set_id, p1_eid, p2_eid)
            if not result.success:
                await add_bot_feed(f"Provider double-DQ failed for match {set_id}: {result.error_message}", "error")
                return {"error": True, "dq_player": "both", "message": result.error_message}
            await add_bot_feed(
                f"⚠️ Double no-show {set_id}: both players DQ'd. start.gg advanced one slot as a "
                "technical resolution (its API can't DQ both) — verify the next round.", "warn"
            )
    elif winner_eid:
        try:
            result = await provider.mark_dq(set_id, winner_eid)
            if not result.success:
                raise Exception(result.error_message or "Unknown provider error")
        except Exception as e:
            await add_bot_feed(f"Provider auto-DQ failed for match {set_id}: {e}", "error")
            # Do not flip local status if provider rejected — keeps states aligned.
            return {"error": True, "dq_player": dq_eid, "message": str(e)}

    await update_active_match(set_id, status="complete", dq_player=dq_eid)
    await hub_mgr.broadcast({"type": "match_update"})
    return {"ok": True, "dq_player": dq_eid}

async def start_call_timer(set_id: str, timeout_seconds: int = 600):
    await asyncio.sleep(timeout_seconds)
    match = await get_active_match(set_id)
    if not match or match.get("status") != "called":
        return
    if match.get("auto_dq_disarmed"):
        await add_bot_feed(
            f"⏰ Call timer expired for {set_id} — auto-DQ disarmed (partial/no Discord reach). "
            "Letting start.gg own this match.",
            "info"
        )
        return
    await add_bot_feed(f"⏰ Call timer expired for match {set_id}, auto-DQ triggered", "warn")
    await auto_dq_match(set_id)
