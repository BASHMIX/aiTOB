"""Workspace-scoped resumable tournament setup drafts.

The draft is the server-owned source of truth for the five-step wizard.  It
contains only validated, non-secret answers; provider credentials and OAuth
state live in their dedicated integration stores.  The repository intentionally
keeps network calls outside its transactions so a stale browser tab cannot
overwrite a newer draft or hold a database connection during provider I/O.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Mapping
from typing import Any

from backend.core import database
from backend.core.storage import dbapi, is_postgres


class DraftError(ValueError):
    """A draft mutation is invalid for its current lifecycle or revision."""


class DraftNotFound(DraftError):
    pass


class DraftRevisionConflict(DraftError):
    def __init__(self, latest: dict[str, Any]):
        super().__init__("draft_version_conflict")
        self.latest = latest


_SECTIONS = {
    "provider_scope",
    "tournament_review",
    "operating_profile",
    "discord_setup",
    "assistant_setup",
    "navigation",
}
_SECRET_KEYS = {
    "api_key", "apikey", "token", "access_token", "refresh_token", "password",
    "authorization", "cookie", "secret", "bot_token", "headers",
}
_STEPS = {"provider", "tournament", "discord", "assistant", "review"}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _iso_timestamp(value: Any) -> str | None:
    """Keep stored strings and PostgreSQL datetime values API-compatible."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.isoformat()
    return str(value)


def _reject_secrets(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _SECRET_KEYS or normalized.endswith(("_token", "_secret", "_password")):
                raise DraftError("secret_field_not_allowed")
            _reject_secrets(nested)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_secrets(item)


def _json(value: Any) -> str:
    _reject_secrets(value)
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise DraftError("draft_value_not_json") from exc


def _loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return fallback


def _row_to_draft(row: Any) -> dict[str, Any]:
    if not row:
        raise DraftNotFound("draft_not_found")
    answers = _loads(row["answers_json"], {})
    completion = _loads(row["completion_json"], {})
    validation = _loads(row.get("validation_json") if hasattr(row, "get") else None, {})
    result = {
        "id": str(row["id"]),
        "workspace_id": str(row["workspace_id"]),
        "revision": int(row["revision"]),
        "status": str(row["status"]),
        "current_step": str(row["current_step"]),
        "completed_steps": completion.get("completed_steps", []) if isinstance(completion, dict) else [],
        "provider_scope": answers.get("provider_scope") if isinstance(answers, dict) else None,
        "tournament_review": answers.get("tournament_review", {}) if isinstance(answers, dict) else {},
        "operating_profile": answers.get("operating_profile", {}) if isinstance(answers, dict) else {},
        "discord_setup": answers.get("discord_setup", {}) if isinstance(answers, dict) else {},
        "assistant_setup": answers.get("assistant_setup", {}) if isinstance(answers, dict) else {},
        "validation": validation if isinstance(validation, dict) else {},
        "materialized_tournament_id": row["materialized_tournament_id"],
        "created_at": _iso_timestamp(row["created_at"]),
        "updated_at": _iso_timestamp(row["updated_at"]),
    }
    # Columns are authoritative for selected resource identities.  They are
    # safe IDs/status, never credentials.
    if result["provider_scope"] is None and row["external_scope_id"]:
        result["provider_scope"] = {
            "provider_account_id": row["provider_account_id"],
            "provider_type": row["provider_type"],
            "external_tournament_id": row["external_tournament_id"],
            "external_scope_id": row["external_scope_id"],
            "external_tournament_slug": row["external_tournament_slug"],
            "external_scope_slug": row["external_scope_slug"],
            "observed_at": _iso_timestamp(row["provider_observed_at"]),
        }
    return result


async def _fetch(db: Any, draft_id: str, workspace_id: str, *, lock: bool = False) -> dict[str, Any]:
    suffix = " FOR UPDATE" if lock and is_postgres() else ""
    row = await (await db.execute(
        "SELECT * FROM tournament_setup_drafts WHERE id=? AND workspace_id=?" + suffix,
        (draft_id, workspace_id),
    )).fetchone()
    return _row_to_draft(row)


async def create_draft(workspace_id: str, actor_id: str, *, template: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not workspace_id or not actor_id:
        raise DraftError("workspace_and_actor_required")
    answers: dict[str, Any] = {}
    if template:
        _reject_secrets(template)
        answers = {key: template[key] for key in ("tournament_review", "operating_profile", "discord_setup") if key in template}
    draft_id = str(uuid.uuid4())
    now = _now()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute(
            """INSERT INTO tournament_setup_drafts
               (id, workspace_id, created_by, updated_by, answers_json, completion_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (draft_id, workspace_id, actor_id, actor_id, _json(answers), _json({"completed_steps": []}), now, now),
        )
        await db.commit()
        return await _fetch(db, draft_id, workspace_id)


async def get_draft(draft_id: str, workspace_id: str) -> dict[str, Any]:
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        return await _fetch(db, draft_id, workspace_id)


async def reopen_draft_for_tournament(tournament_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
    """Reopen the materialized wizard draft that owns a Hub tournament.

    Materialized drafts are normally immutable so a completed setup cannot be
    changed by a stale browser tab.  An explicit Edit action is the deliberate
    exception: it advances the revision and returns the same draft in the
    editable state.  Re-materializing it projects the updated answers back to
    the existing tournament instead of creating a second Hub card.
    """
    tournament_id = str(tournament_id or "").strip()
    if not tournament_id:
        raise DraftNotFound("draft_not_found")
    now = _now()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            suffix = " FOR UPDATE" if is_postgres() else ""
            row = await (await db.execute(
                "SELECT * FROM tournament_setup_drafts "
                "WHERE materialized_tournament_id=? AND workspace_id=? "
                "ORDER BY updated_at DESC LIMIT 1" + suffix,
                (tournament_id, workspace_id),
            )).fetchone()
            if not row:
                raise DraftNotFound("draft_not_found")
            await db.execute(
                """UPDATE tournament_setup_drafts
                   SET status='editing', current_step='provider',
                       revision=revision+1, updated_by=?, updated_at=?
                   WHERE id=? AND workspace_id=?""",
                (actor_id, now, str(row["id"]), workspace_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return await _fetch(db, str(row["id"]), workspace_id)


async def list_drafts(workspace_id: str, *, statuses: set[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
    bounded_limit = max(1, min(int(limit), 100))
    params: list[Any] = [workspace_id]
    where = "workspace_id=?"
    if statuses:
        allowed = sorted(set(statuses) & {"editing", "ready", "materialized", "abandoned"})
        if not allowed:
            return []
        where += " AND status IN (" + ",".join("?" for _ in allowed) + ")"
        params.extend(allowed)
    params.append(bounded_limit)
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        rows = await (await db.execute(
            "SELECT * FROM tournament_setup_drafts WHERE " + where + " ORDER BY updated_at DESC LIMIT ?", params
        )).fetchall()
        return [_row_to_draft(row) for row in rows]


async def patch_draft(
    draft_id: str,
    workspace_id: str,
    actor_id: str,
    *,
    section: str,
    value: Mapping[str, Any] | None = None,
    expected_revision: int,
    current_step: str | None = None,
) -> dict[str, Any]:
    if section not in _SECTIONS:
        raise DraftError("unknown_draft_section")
    if current_step is not None and current_step not in _STEPS:
        raise DraftError("unknown_wizard_step")
    payload = dict(value or {})
    _reject_secrets(payload)
    now = _now()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            row = await (await db.execute(
                "SELECT * FROM tournament_setup_drafts WHERE id=? AND workspace_id=?" + (" FOR UPDATE" if is_postgres() else ""),
                (draft_id, workspace_id),
            )).fetchone()
            latest = _row_to_draft(row)
            if latest["status"] in {"materialized", "abandoned"}:
                raise DraftError("draft_not_editable")
            if int(row["revision"]) != int(expected_revision):
                raise DraftRevisionConflict(latest)
            answers = _loads(row["answers_json"], {})
            if not isinstance(answers, dict):
                answers = {}
            if section != "navigation":
                answers[section] = payload
            completion = _loads(row["completion_json"], {})
            if not isinstance(completion, dict):
                completion = {}
            if current_step and current_step not in completion.get("completed_steps", []):
                completed = list(completion.get("completed_steps", []))
                # A server-side step change never marks a step complete unless
                # the caller has supplied a non-empty, validated section.
                if section != "navigation" and payload and current_step not in completed:
                    completed.append(current_step)
                completion["completed_steps"] = completed
            new_step = current_step or latest["current_step"]
            await db.execute(
                """UPDATE tournament_setup_drafts
                   SET answers_json=?, completion_json=?, current_step=?, status='editing',
                       revision=revision+1, updated_by=?, updated_at=?
                   WHERE id=? AND workspace_id=?""",
                (_json(answers), _json(completion), new_step, actor_id, now, draft_id, workspace_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return await _fetch(db, draft_id, workspace_id)


async def abandon_draft(draft_id: str, workspace_id: str, *, expected_revision: int) -> None:
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("BEGIN")
        try:
            row = await (await db.execute(
                "SELECT status, revision FROM tournament_setup_drafts WHERE id=? AND workspace_id=?" + (" FOR UPDATE" if is_postgres() else ""),
                (draft_id, workspace_id),
            )).fetchone()
            if not row:
                raise DraftNotFound("draft_not_found")
            if int(row[1]) != int(expected_revision):
                raise DraftError("draft_version_conflict")
            if str(row[0]) == "materialized":
                raise DraftError("draft_not_editable")
            await db.execute(
                "UPDATE tournament_setup_drafts SET status='abandoned', revision=revision+1, updated_at=? WHERE id=? AND workspace_id=?",
                (_now(), draft_id, workspace_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def update_provider_scope(
    draft_id: str,
    workspace_id: str,
    actor_id: str,
    *,
    expected_revision: int,
    provider_account_id: str,
    provider_type: str,
    external_tournament_id: str,
    external_scope_id: str,
    external_tournament_slug: str | None = None,
    external_scope_slug: str | None = None,
    provider_observed_at: str | None = None,
) -> dict[str, Any]:
    if provider_type not in {"startgg", "challonge"}:
        raise DraftError("unsupported_provider")
    now = _now()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            row = await (await db.execute(
                "SELECT * FROM tournament_setup_drafts WHERE id=? AND workspace_id=?" + (" FOR UPDATE" if is_postgres() else ""),
                (draft_id, workspace_id),
            )).fetchone()
            latest = _row_to_draft(row)
            if latest["status"] in {"materialized", "abandoned"}:
                raise DraftError("draft_not_editable")
            if int(row["revision"]) != int(expected_revision):
                raise DraftRevisionConflict(latest)
            await db.execute(
                """UPDATE tournament_setup_drafts SET provider_account_id=?, provider_type=?,
                   external_tournament_id=?, external_scope_id=?, external_tournament_slug=?,
                   external_scope_slug=?, provider_observed_at=?, revision=revision+1,
                   updated_by=?, updated_at=?, status='editing' WHERE id=? AND workspace_id=?""",
                (provider_account_id, provider_type, external_tournament_id, external_scope_id,
                 external_tournament_slug, external_scope_slug, provider_observed_at,
                 actor_id, now, draft_id, workspace_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return await _fetch(db, draft_id, workspace_id)
