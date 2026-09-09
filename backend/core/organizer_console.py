"""Database-only read projection for the Organizer Console."""
from __future__ import annotations

from datetime import UTC, datetime
from backend.core.storage import dbapi as aiosqlite

from backend.core import database
from backend.core.action_proposals import list_action_proposals
from backend.core.timestamps import as_utc


def _alive(value: str | None) -> bool:
    try:
        if not value:
            return False
        instant = as_utc(value)
        return 0 <= (datetime.now(UTC) - instant).total_seconds() <= 45
    except (TypeError, ValueError):
        return False


async def read_organizer_console(tournament_slug: str, workspace_id: str | None = None) -> dict:
    """Build a safe, tournament-scoped view without touching any integration."""
    tournament = await database.get_tournament(tournament_slug, workspace_id)
    if not tournament:
        raise ValueError("Tournament not found")
    master = (await database.get_setting("auto_dispatch_master_switch", "off") or "off").lower() == "on"
    heartbeat = await database.get_setting("auto_dispatcher_last_seen", None)
    configured = bool(tournament.get("auto_dispatch_enabled"))
    if not configured:
        dispatch_state = "paused_tournament"
    elif not master:
        dispatch_state = "paused_global"
    elif not _alive(heartbeat):
        dispatch_state = "service_offline"
    else:
        dispatch_state = "running"

    matches = await database.get_active_matches(tournament_slug, workspace_id=workspace_id)
    active = sum(str(row.get("status") or "") in {"called", "ready", "in_progress"} for row in matches)
    capacity = max(1, int(tournament.get("auto_dispatch_concurrency") or 1))
    proposals = await list_action_proposals(tournament_slug, workspace_id)

    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        conflicts = [dict(row) for row in await (await db.execute(
            """SELECT c.id, c.set_id, c.created_at, am.p1_name, am.p2_name
               FROM conflicts c JOIN active_matches am ON am.set_id=c.set_id
               WHERE c.resolved=FALSE AND am.tournament_slug=? AND (? IS NULL OR am.workspace_id=?) ORDER BY c.created_at DESC""", (tournament_slug, workspace_id, workspace_id)
        )).fetchall()]
        provider_commands = [dict(row) for row in await (await db.execute(
            """SELECT id, set_id, action, state, reason, error_message, created_at, updated_at
               FROM provider_command_ledger WHERE tournament_slug=? AND (? IS NULL OR workspace_id=?) ORDER BY updated_at DESC LIMIT 100""", (tournament_slug, workspace_id, workspace_id)
        )).fetchall()]
        decisions = [dict(row) for row in await (await db.execute(
            """SELECT id, event_id, set_id, decision, reason_code, explanation, first_seen_at, last_seen_at, seen_count
               FROM dispatcher_decisions WHERE tournament_slug=? AND (? IS NULL OR workspace_id=?) ORDER BY last_seen_at DESC LIMIT 100""", (tournament_slug, workspace_id, workspace_id)
        )).fetchall()]
        outbox = [dict(row) for row in await (await db.execute(
            """SELECT o.event_id, o.match_id, o.event_type, o.status, o.attempts, o.created_at, o.updated_at, o.completed_at
               FROM workflow_outbox o LEFT JOIN active_matches am ON am.set_id=o.match_id
               LEFT JOIN action_proposals ap ON ap.outbox_event_id=o.event_id
               WHERE (am.tournament_slug=? OR ap.tournament_slug=?) AND (? IS NULL OR o.workspace_id=?)
               ORDER BY o.updated_at DESC LIMIT 100""", (tournament_slug, tournament_slug, workspace_id, workspace_id)
        )).fetchall()]
        commands = [dict(row) for row in await (await db.execute(
            """SELECT hc.id, hc.source, hc.status, hc.created_at, ap.id AS proposal_id, ap.match_id
               FROM hub_commands hc JOIN action_proposals ap ON ap.command_id=hc.id
               WHERE ap.tournament_slug=? AND (? IS NULL OR hc.workspace_id=?) ORDER BY hc.created_at DESC LIMIT 100""", (tournament_slug, workspace_id, workspace_id)
        )).fetchall()]

    failed_commands = [row for row in provider_commands if row["state"] in {"failed", "permanent_failure", "conflict", "needs_review"}]
    waiting_verification = [row for row in provider_commands if row["state"] in {"pending", "sending", "acknowledged", "retryable"}]
    timeline = []
    timeline += [{"kind": "proposal", "id": row["id"], "at": row["created_at"], "status": row["approval_status"], "action": row["action_type"], "match_id": row.get("match_id"), "command_id": row.get("command_id"), "outbox_event_id": row.get("outbox_event_id")} for row in proposals]
    timeline += [{"kind": "hub_command", "id": row["id"], "at": row["created_at"], "status": row["status"], "source": row["source"], "proposal_id": row.get("proposal_id"), "match_id": row.get("match_id")} for row in commands]
    timeline += [{"kind": "outbox", "id": row["event_id"], "at": row["updated_at"] or row["created_at"], "status": row["status"], "event_type": row["event_type"], "match_id": row["match_id"]} for row in outbox]
    timeline += [{"kind": "provider_command", "id": row["id"], "at": row["updated_at"] or row["created_at"], "status": row["state"], "action": row["action"], "match_id": row["set_id"]} for row in provider_commands]
    timeline.sort(key=lambda row: str(row.get("at") or ""), reverse=True)
    return {
        "tournament": {"slug": tournament_slug, "name": tournament.get("name"), "provider_type": tournament.get("provider_type")},
        "refreshed_at": datetime.now(UTC).isoformat(),
        "attention": {
            "conflicts": conflicts, "failed_commands": failed_commands,
            "awaiting_verification": waiting_verification,
            "provider_outage": {"active": tournament.get("provider_sync_status") == "error", "message": tournament.get("provider_sync_error")},
        },
        "dispatch": {"state": dispatch_state, "configured": configured, "service_alive": _alive(heartbeat), "slots_available": max(0, capacity - active), "active_slots": active, "capacity": capacity, "decisions": decisions},
        "approvals": [{key: row.get(key) for key in ("id", "match_id", "action_type", "reason", "approval_status", "execution_status", "command_id", "outbox_event_id", "expires_at")} for row in proposals],
        "timeline": timeline[:200],
    }
