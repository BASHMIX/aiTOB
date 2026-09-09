"""Reviewed organizer actions, intentionally independent from every AI model.

Only two actions are supported in this first slice: Call and an announcement
draft.  Creating a proposal is storage-only.  A separately authenticated
organizer must approve it before the normal Hub command/outbox paths run.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.core.storage import dbapi as aiosqlite
from backend.core.storage import is_postgres

from backend.core import database

ACTION_TYPES = {"call", "announcement_draft"}
DEFAULT_ORGANIZER_ID = "hub_admin"  # Current Hub auth is one administrator identity.
AI_SERVICE_ACTOR = "ai_service"


class ProposalError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _canonical_snapshot(tournament_slug: str, match: dict | None) -> dict:
    if not match:
        return {"tournament_slug": tournament_slug}
    return {
        "tournament_slug": tournament_slug,
        "match_id": str(match.get("set_id") or ""),
        "status": str(match.get("status") or "not_started"),
        "hub_status": str(match.get("hub_status") or ""),
        "provider_state": str(match.get("provider_state_normalized") or match.get("provider_state") or ""),
        "p1_entrant_id": str(match.get("p1_entrant_id") or ""),
        "p2_entrant_id": str(match.get("p2_entrant_id") or ""),
        "p1_name": str(match.get("p1_name") or ""),
        "p2_name": str(match.get("p2_name") or ""),
        "is_stream_match": bool(match.get("is_stream_match")),
    }


def _version(snapshot: dict) -> str:
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _authorized(tournament_slug: str, actor: str, *, workspace_id: str | None = None, allow_ai_creator: bool = False) -> None:
    # The current Hub has password-authenticated admin only; do not accept an
    # arbitrary `created_by`/`approved_by` value from a browser or an Assistant.
    if workspace_id is None:
        if actor != DEFAULT_ORGANIZER_ID and not (allow_ai_creator and actor == AI_SERVICE_ACTOR):
            raise ProposalError("Organizer authorization is required for this tournament")
    elif not (allow_ai_creator and actor == AI_SERVICE_ACTOR):
        async with aiosqlite.connect(database.DB_PATH) as db:
            member = await (await db.execute(
                """SELECT role FROM workspace_memberships
                   WHERE workspace_id=? AND user_id=? AND status='active'""",
                (workspace_id, actor),
            )).fetchone()
        from backend.core.workspace_auth import permission_allowed
        if not member or not permission_allowed(str(member[0]), "proposal.review"):
            raise ProposalError("Organizer authorization is required for this tournament")
    if not await database.get_tournament(tournament_slug, workspace_id):
        raise ProposalError("Tournament not found")


async def _proposal_row(proposal_id: str, workspace_id: str | None = None) -> dict | None:
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        lock = " FOR UPDATE" if is_postgres() else ""
        query, params = "SELECT * FROM action_proposals WHERE id=?", (proposal_id,)
        if workspace_id is not None:
            query, params = query + " AND workspace_id=?", params + (workspace_id,)
        row = await (await db.execute(query + lock, params)).fetchone()
    return dict(row) if row else None


async def create_action_proposal(*, tournament_slug: str, action_type: str, reason: str,
                                 payload: dict | None = None, match_id: str | None = None,
                                 expires_in_seconds: int = 900, actor: str = DEFAULT_ORGANIZER_ID,
                                 workspace_id: str | None = None) -> dict:
    """Persist a proposed action without creating any command or external effect."""
    await _authorized(tournament_slug, actor, workspace_id=workspace_id, allow_ai_creator=actor == AI_SERVICE_ACTOR)
    if action_type not in ACTION_TYPES:
        raise ProposalError("Unsupported proposal action")
    if not reason.strip():
        raise ProposalError("A reason is required")
    if not 60 <= int(expires_in_seconds) <= 86_400:
        raise ProposalError("Proposal expiry must be between 60 seconds and 24 hours")
    if action_type == "call" and not match_id:
        raise ProposalError("A Call proposal needs a match")
    if action_type == "announcement_draft" and not str((payload or {}).get("text") or "").strip():
        raise ProposalError("An announcement draft needs text")

    match = None
    if match_id:
        match = await database.get_active_match(match_id, workspace_id)
        if not match or match.get("tournament_slug") != tournament_slug:
            raise ProposalError("Match does not belong to this tournament")
    snapshot = _canonical_snapshot(tournament_slug, match)
    created = _now()
    proposal = {
        "id": str(uuid4()), "workspace_id": workspace_id, "tournament_slug": tournament_slug, "match_id": match_id,
        "action_type": action_type, "payload_json": json.dumps(payload or {}),
        "reason": reason.strip(), "created_by": actor, "created_at": _iso(created),
        "expires_at": _iso(created + timedelta(seconds=int(expires_in_seconds))),
        "state_version": _version(snapshot), "state_snapshot_json": json.dumps(snapshot, sort_keys=True),
    }
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute(
            """INSERT INTO action_proposals (
                id,workspace_id,tournament_slug,match_id,action_type,payload_json,reason,created_by,created_at,expires_at,state_version,state_snapshot_json
            ) VALUES (:id,:workspace_id,:tournament_slug,:match_id,:action_type,:payload_json,:reason,:created_by,:created_at,:expires_at,:state_version,:state_snapshot_json)""",
            proposal,
        )
        await db.commit()
    return await _proposal_row(proposal["id"], workspace_id) or proposal


async def list_action_proposals(tournament_slug: str, workspace_id: str | None = None) -> list[dict]:
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT * FROM action_proposals WHERE tournament_slug=? AND (? IS NULL OR workspace_id=?) ORDER BY created_at DESC",
            (tournament_slug, workspace_id, workspace_id),
        )).fetchall()
    return [dict(row) for row in rows]


async def reject_action_proposal(proposal_id: str, *, actor: str = DEFAULT_ORGANIZER_ID,
                                 reason: str = "Rejected by organizer", workspace_id: str | None = None) -> dict:
    proposal = await _proposal_row(proposal_id, workspace_id)
    if not proposal:
        raise ProposalError("Proposal not found")
    await _authorized(proposal["tournament_slug"], actor, workspace_id=workspace_id)
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """UPDATE action_proposals SET approval_status='rejected', rejected_by=?, rejected_at=?, rejection_reason=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND approval_status='pending'""",
            (actor, _iso(_now()), reason.strip() or "Rejected by organizer", proposal_id),
        )
        if cursor.rowcount != 1:
            await db.rollback()
            return await _proposal_row(proposal_id, workspace_id) or proposal
        await db.commit()
    return await _proposal_row(proposal_id, workspace_id) or proposal


async def _fresh_snapshot_for_proposal(db: aiosqlite.Connection, proposal: dict) -> tuple[dict, str]:
    match = None
    if proposal.get("match_id"):
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM active_matches WHERE set_id=?"
        params = (proposal["match_id"],)
        if proposal.get("workspace_id") is not None:
            query += " AND workspace_id=?"
            params += (proposal["workspace_id"],)
        row = await (await db.execute(query, params)).fetchone()
        match = dict(row) if row else None
        if not match or match.get("tournament_slug") != proposal["tournament_slug"]:
            raise ProposalError("Match is no longer available in this tournament")
    snapshot = _canonical_snapshot(proposal["tournament_slug"], match)
    return snapshot, _version(snapshot)


def _call_is_eligible(match: dict | None) -> bool:
    if not match or str(match.get("status") or "not_started") != "not_started":
        return False
    names = (str(match.get("p1_name") or "").strip().lower(), str(match.get("p2_name") or "").strip().lower())
    entrants = (str(match.get("p1_entrant_id") or "").strip(), str(match.get("p2_entrant_id") or "").strip())
    return all(names) and all(entrants) and not any(name in {"tbd", "bye"} for name in names)


async def approve_action_proposal(proposal_id: str, *, actor: str = DEFAULT_ORGANIZER_ID,
                                  workspace_id: str | None = None) -> dict:
    """Approve atomically with one durable Hub executor command.

    The command is only an execution request; it never signifies a completed
    Call or delivered announcement.  A unique command_id plus BEGIN IMMEDIATE
    makes repeated/concurrent approvals harmless.
    """
    proposal = await _proposal_row(proposal_id, workspace_id)
    if not proposal:
        raise ProposalError("Proposal not found")
    await _authorized(proposal["tournament_slug"], actor, workspace_id=workspace_id)
    should_notify = False
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if is_postgres() else ""
        row = await (await db.execute("SELECT * FROM action_proposals WHERE id=?" + lock, (proposal_id,))).fetchone()
        if not row:
            await db.rollback()
            raise ProposalError("Proposal not found")
        current = dict(row)
        if current["approval_status"] != "pending":
            await db.rollback()
            return current
        expiry = current["expires_at"]
        expiry = expiry if isinstance(expiry, datetime) else datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
        expiry = expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry.astimezone(UTC)
        if _now() >= expiry:
            await db.execute("UPDATE action_proposals SET approval_status='expired', updated_at=CURRENT_TIMESTAMP WHERE id=?", (proposal_id,))
            await db.commit()
            return await _proposal_row(proposal_id) or current
        try:
            snapshot, version = await _fresh_snapshot_for_proposal(db, current)
        except ProposalError:
            snapshot, version = {}, "missing"
        match_query = "SELECT * FROM active_matches WHERE set_id=?"
        match_params = (current["match_id"],)
        if current.get("workspace_id") is not None:
            match_query += " AND workspace_id=?"
            match_params += (current["workspace_id"],)
        match = snapshot and (await (await db.execute(match_query, match_params)).fetchone())
        if version != current["state_version"] or (current["action_type"] == "call" and not _call_is_eligible(dict(match) if match else None)):
            await db.execute(
                "UPDATE action_proposals SET approval_status='needs_review', execution_status='blocked', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (proposal_id,),
            )
            await db.commit()
            return await _proposal_row(proposal_id, workspace_id) or current
        command = await db.execute(
            "INSERT INTO hub_commands (command_text, source, status, workspace_id) VALUES (?, 'proposal', 'pending', ?) RETURNING id",
            (f"execute_action_proposal {proposal_id}", workspace_id),
        )
        command_id = (await command.fetchone())[0]
        await db.execute(
            """UPDATE action_proposals SET approval_status='approved', execution_status='queued', approved_by=?, approved_at=?, command_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (actor, _iso(_now()), command_id, proposal_id),
        )
        await db.commit()
        should_notify = True
    if should_notify:
        database._fire_hub_command_listener()
    return await _proposal_row(proposal_id, workspace_id) or proposal


async def _mark_execution(
    proposal_id: str, status: str, error: str | None = None,
    *, workspace_id: str | None = None,
) -> dict:
    async with aiosqlite.connect(database.DB_PATH) as db:
        query = "UPDATE action_proposals SET execution_status=?, execution_error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        params = (status, error, proposal_id)
        if workspace_id is not None:
            query += " AND workspace_id=?"
            params += (workspace_id,)
        await db.execute(query, params)
        await db.commit()
    return await _proposal_row(proposal_id, workspace_id) or {}


async def execute_approved_proposal(proposal_id: str, *, workspace_id: str | None = None) -> dict:
    """Run a previously approved proposal through the established local paths."""
    proposal = await _proposal_row(proposal_id, workspace_id)
    if not proposal:
        raise ProposalError("Proposal not found")
    if proposal["approval_status"] != "approved":
        return proposal
    if proposal["execution_status"] in {"workflow_started", "outbox_queued"}:
        return proposal
    if proposal["execution_status"] != "queued":
        return proposal
    await _mark_execution(proposal_id, "executing", workspace_id=workspace_id)
    # Revalidate immediately before the effect path as well as at approval.
    current = await _proposal_row(proposal_id, workspace_id)
    if not current:
        raise ProposalError("Proposal not found")
    match = await database.get_active_match(current["match_id"], workspace_id) if current.get("match_id") else None
    if _version(_canonical_snapshot(current["tournament_slug"], match)) != current["state_version"]:
        async with aiosqlite.connect(database.DB_PATH) as db:
            await db.execute("UPDATE action_proposals SET approval_status='needs_review', execution_status='blocked', updated_at=CURRENT_TIMESTAMP WHERE id=?", (proposal_id,))
            await db.commit()
        return await _proposal_row(proposal_id, workspace_id) or current
    if current["action_type"] == "call":
        if not _call_is_eligible(match):
            return await _mark_execution(
                proposal_id, "blocked", "Match is no longer eligible to call", workspace_id=workspace_id,
            )
        from backend.core.match_state import call_match_core
        result = await call_match_core(
            str(current["match_id"]), source="proposal", workspace_id=workspace_id,
        )
        if result.get("error"):
            return await _mark_execution(
                proposal_id, "failed", str(result["error"]), workspace_id=workspace_id,
            )
        return await _mark_execution(proposal_id, "workflow_started", workspace_id=workspace_id)

    payload = json.loads(current["payload_json"] or "{}")
    event_id = str(uuid4())
    deduplication_key = f"proposal-announcement:{proposal_id}"
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """INSERT INTO workflow_outbox (event_id, workspace_id, match_id, event_type, payload_json, deduplication_key, status, attempts)
               VALUES (?, ?, ?, 'discord_announcement', ?, ?, 'pending', 0)
               ON CONFLICT(deduplication_key) DO NOTHING""",
            (event_id, workspace_id, current.get("match_id") or f"proposal:{proposal_id}", json.dumps({"tournament_slug": current["tournament_slug"], "text": payload.get("text", "")}), deduplication_key),
        )
        row = await (await db.execute("SELECT event_id FROM workflow_outbox WHERE deduplication_key=?", (deduplication_key,))).fetchone()
        await db.execute(
            "UPDATE action_proposals SET execution_status='outbox_queued', outbox_event_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (row[0], proposal_id),
        )
        await db.commit()
    return await _proposal_row(proposal_id, workspace_id) or current
