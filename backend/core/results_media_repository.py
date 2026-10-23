"""Workspace-scoped PostgreSQL repository for Tournament Results Media."""

from __future__ import annotations

import json
import uuid
from typing import Any, Mapping
from backend.core.storage import dbapi
from backend.core import database


def _uuid() -> str:
    return str(uuid.uuid4())


def _json_dumps(val: Any) -> str:
    if isinstance(val, str):
        return val
    return json.dumps(val or ({} if isinstance(val, dict) else []))


def _json_loads(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return val


# ── Result Versions and Entries ──────────────────────────────────────────────

async def create_result_version_with_entries(
    workspace_id: str,
    version_data: Mapping[str, Any],
    entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Persist an immutable result version and its entries in one short transaction."""
    v_id = str(version_data.get("id") or _uuid())
    ordinals = [int(entry["ordinal"]) for entry in entries]
    entrant_ids = [str(entry["entrant_id"]) for entry in entries]
    if len(ordinals) != len(set(ordinals)):
        raise ValueError("result standings contain duplicate ordinals")
    if len(entrant_ids) != len(set(entrant_ids)):
        raise ValueError("result standings contain duplicate entrant ids")

    created_new = False
    async with dbapi.connect(database.DATABASE_DSN) as db:
        lock_key = ":".join((
            workspace_id,
            str(version_data["tournament_slug"]),
            str(version_data["event_id"]),
            str(version_data["observation_hash"]),
        ))
        await db.execute("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", (lock_key,))
        existing = await (await db.execute(
            """SELECT id FROM tournament_result_versions
               WHERE workspace_id=? AND tournament_slug=? AND event_id=? AND observation_hash=?""",
            (
                workspace_id,
                version_data["tournament_slug"],
                version_data["event_id"],
                version_data["observation_hash"],
            ),
        )).fetchone()

        if existing:
            v_id = str(existing[0])
        else:
            created_new = True
            await db.execute(
            """INSERT INTO tournament_result_versions (
                id, workspace_id, tournament_slug, provider_type,
                provider_account_id, provider_tournament_id, event_id, event_name,
                game_id, game_name, capture_status, provider_state_raw,
                provider_revision, provider_payload_hash, presentation_hash,
                observation_hash, observed_at, finalized_at, warning_json,
                event_metadata_json, entry_count, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                v_id,
                workspace_id,
                version_data["tournament_slug"],
                version_data["provider_type"],
                version_data["provider_account_id"],
                version_data["provider_tournament_id"],
                version_data["event_id"],
                version_data["event_name"],
                version_data.get("game_id"),
                version_data.get("game_name"),
                version_data["capture_status"],
                version_data["provider_state_raw"],
                version_data.get("provider_revision"),
                version_data["provider_payload_hash"],
                version_data["presentation_hash"],
                version_data["observation_hash"],
                version_data["observed_at"],
                version_data.get("finalized_at"),
                _json_dumps(version_data.get("warning_json", [])),
                _json_dumps(version_data.get("event_metadata_json", {})),
                len(entries),
                version_data["created_by"],
            ),
            )

            for entry in entries:
                await db.execute(
                """INSERT INTO tournament_result_entries (
                    version_id, workspace_id, ordinal, placement, entrant_id,
                    entrant_name, provider_user_id, player_profile_id, is_tied,
                    presentation_json, provider_entry_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    v_id,
                    workspace_id,
                    entry["ordinal"],
                    entry["placement"],
                    entry["entrant_id"],
                    entry["entrant_name"],
                    entry.get("provider_user_id"),
                    entry.get("player_profile_id"),
                    entry.get("is_tied", False),
                    _json_dumps(entry.get("presentation_json", entry.get("presentation", {}))),
                    _json_dumps(entry.get("provider_entry_json", entry.get("provider_entry", {}))),
                ),
                )

            if version_data.get("_audit_action"):
                await db.execute(
                    """INSERT INTO audit_events
                       (id, workspace_id, actor_id, action, target_type, target_id,
                        outcome, detail_json)
                       VALUES (?, ?, ?, ?, 'tournament_result_version', ?, 'success', ?)""",
                    (
                        _uuid(),
                        workspace_id,
                        version_data["created_by"],
                        str(version_data["_audit_action"]),
                        v_id,
                        _json_dumps({
                            "tournament_slug": version_data["tournament_slug"],
                            "event_id": version_data["event_id"],
                            "capture_status": version_data["capture_status"],
                            "entry_count": len(entries),
                        }),
                    ),
                )

        await db.commit()

    result = await get_result_version_by_id(workspace_id, v_id) or {}
    result["_created"] = created_new
    return result


async def get_result_version_by_id(workspace_id: str, version_id: str) -> dict[str, Any] | None:
    """Retrieve an immutable result version by ID strictly scoped to workspace."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            """SELECT
                id, workspace_id, tournament_slug, provider_type,
                provider_account_id, provider_tournament_id, event_id, event_name,
                game_id, game_name, capture_status, provider_state_raw,
                provider_revision, provider_payload_hash, presentation_hash,
                observation_hash, observed_at, finalized_at, warning_json,
                event_metadata_json, entry_count, created_by, created_at
            FROM tournament_result_versions
            WHERE workspace_id = ? AND id = ?
            """,
            (workspace_id, version_id),
        )).fetchone()

        if not row:
            return None

        return _row_to_version_dict(row)


async def get_latest_result_version(
    workspace_id: str,
    tournament_slug: str,
    event_id: str,
) -> dict[str, Any] | None:
    """Retrieve the latest observed result version for an event in a workspace."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            """SELECT
                id, workspace_id, tournament_slug, provider_type,
                provider_account_id, provider_tournament_id, event_id, event_name,
                game_id, game_name, capture_status, provider_state_raw,
                provider_revision, provider_payload_hash, presentation_hash,
                observation_hash, observed_at, finalized_at, warning_json,
                event_metadata_json, entry_count, created_by, created_at
            FROM tournament_result_versions
            WHERE workspace_id = ? AND tournament_slug = ? AND event_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (workspace_id, tournament_slug, event_id),
        )).fetchone()

        if not row:
            return None

        return _row_to_version_dict(row)


async def get_result_version_by_hash(
    workspace_id: str,
    tournament_slug: str,
    event_id: str,
    observation_hash: str,
) -> dict[str, Any] | None:
    """Find an existing version by observation hash for deduplication."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            """SELECT
                id, workspace_id, tournament_slug, provider_type,
                provider_account_id, provider_tournament_id, event_id, event_name,
                game_id, game_name, capture_status, provider_state_raw,
                provider_revision, provider_payload_hash, presentation_hash,
                observation_hash, observed_at, finalized_at, warning_json,
                event_metadata_json, entry_count, created_by, created_at
            FROM tournament_result_versions
            WHERE workspace_id = ? AND tournament_slug = ? AND event_id = ? AND observation_hash = ?
            LIMIT 1
            """,
            (workspace_id, tournament_slug, event_id, observation_hash),
        )).fetchone()

        if not row:
            return None

        return _row_to_version_dict(row)


async def get_version_entries(
    workspace_id: str,
    version_id: str,
    cutoff: str = "top8",
    page: int = 1,
    page_size: int = 16,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retrieve ordered standing entries with cutoff and pagination support."""
    placement_clause = ""
    params: list[Any] = [workspace_id, version_id]

    if cutoff == "top8":
        placement_clause = "AND placement <= 8"
    elif cutoff == "top16":
        placement_clause = "AND placement <= 16"

    offset = max(0, (page - 1) * page_size)

    async with dbapi.connect(database.DATABASE_DSN) as db:
        # Count total entries for this cutoff
        count_query = f"""SELECT COUNT(*)
            FROM tournament_result_entries
            WHERE workspace_id = ? AND version_id = ? {placement_clause}
        """
        count_row = await (await db.execute(count_query, (workspace_id, version_id))).fetchone()
        total_entries = int(count_row[0]) if count_row else 0

        # Query entries
        select_query = f"""SELECT
                version_id, workspace_id, ordinal, placement, entrant_id,
                entrant_name, provider_user_id, player_profile_id, is_tied,
                presentation_json, provider_entry_json
            FROM tournament_result_entries
            WHERE workspace_id = ? AND version_id = ? {placement_clause}
            ORDER BY placement ASC, ordinal ASC
            LIMIT ? OFFSET ?
        """
        rows = await (await db.execute(select_query, (workspace_id, version_id, page_size, offset))).fetchall()

        entries = []
        for r in rows:
            entries.append({
                "version_id": str(r[0]),
                "workspace_id": str(r[1]),
                "ordinal": int(r[2]),
                "placement": int(r[3]),
                "entrant_id": str(r[4]),
                "entrant_name": str(r[5]),
                "provider_user_id": r[6],
                "player_profile_id": r[7],
                "is_tied": bool(r[8]),
                "presentation": _json_loads(r[9]),
                "provider_entry_json": _json_loads(r[10]),
            })

        has_more = (offset + len(entries)) < total_entries
        page_meta = {
            "number": page,
            "size": page_size,
            "total_entries": total_entries,
            "has_more": has_more,
        }

        return entries, page_meta


def _row_to_version_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "workspace_id": str(row[1]),
        "tournament_slug": str(row[2]),
        "provider_type": str(row[3]),
        "provider_account_id": str(row[4]),
        "provider_tournament_id": str(row[5]),
        "event_id": str(row[6]),
        "event_name": str(row[7]),
        "game_id": row[8],
        "game_name": row[9],
        "capture_status": str(row[10]),
        "provider_state_raw": str(row[11]),
        "provider_revision": row[12],
        "provider_payload_hash": str(row[13]),
        "presentation_hash": str(row[14]),
        "observation_hash": str(row[15]),
        "observed_at": str(row[16]),
        "finalized_at": str(row[17]) if row[17] else None,
        "warnings": _json_loads(row[18]) or [],
        "event_metadata": _json_loads(row[19]) or {},
        "entry_count": int(row[20]),
        "created_by": str(row[21]),
        "created_at": str(row[22]),
    }


# ── Results Media Outputs ───────────────────────────────────────────────────

async def create_media_output(workspace_id: str, output_data: Mapping[str, Any]) -> dict[str, Any]:
    """Persist an immutable results media output receipt."""
    out_id = str(output_data.get("id") or _uuid())
    async with dbapi.connect(database.DATABASE_DSN) as db:
        scene_cfg = output_data.get("scene_config_json") if "scene_config_json" in output_data else output_data.get("scene_config", {})
        profile_cfg = output_data.get("output_profile_json") if "output_profile_json" in output_data else output_data.get("output_profile", {})
        await db.execute(
            """INSERT INTO results_media_outputs (
                id, workspace_id, result_version_id, output_kind, overlay_name,
                scene_schema_version, scene_config_json, scene_hash, cutoff,
                page_number, output_profile_json, export_byte_size, export_sha256,
                created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                out_id,
                workspace_id,
                output_data["result_version_id"],
                output_data["output_kind"],
                output_data.get("overlay_name"),
                output_data.get("scene_schema_version", 2),
                _json_dumps(scene_cfg),
                output_data["scene_hash"],
                output_data["cutoff"],
                output_data.get("page_number", 1),
                _json_dumps(profile_cfg),
                output_data.get("export_byte_size"),
                output_data.get("export_sha256"),
                output_data["created_by"],
            ),
        )
        await db.commit()

    return await get_media_output(workspace_id, out_id) or {}


async def get_media_output(workspace_id: str, output_id: str) -> dict[str, Any] | None:
    """Retrieve a media output receipt scoped to workspace."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            """SELECT
                id, workspace_id, result_version_id, output_kind, overlay_name,
                scene_schema_version, scene_config_json, scene_hash, cutoff,
                page_number, output_profile_json, export_byte_size, export_sha256,
                created_by, created_at
            FROM results_media_outputs
            WHERE workspace_id = ? AND id = ?
            """,
            (workspace_id, output_id),
        )).fetchone()

        if not row:
            return None

        return {
            "id": str(row[0]),
            "workspace_id": str(row[1]),
            "result_version_id": str(row[2]),
            "output_kind": str(row[3]),
            "overlay_name": row[4],
            "scene_schema_version": int(row[5]),
            "scene_config": _json_loads(row[6]),
            "scene_hash": str(row[7]),
            "cutoff": str(row[8]),
            "page_number": int(row[9]),
            "output_profile": _json_loads(row[10]),
            "export_byte_size": int(row[11]) if row[11] is not None else None,
            "export_sha256": row[12],
            "created_by": str(row[13]),
            "created_at": str(row[14]),
        }


async def record_export_receipt(
    workspace_id: str,
    output_id: str,
    byte_size: int,
    sha256: str,
) -> str:
    """Record an immutable client PNG receipt.

    Returns ``recorded``, ``unchanged``, ``conflict``, or ``not_found`` so the
    API can distinguish safe idempotent retry from an attempted rewrite.
    """
    async with dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            """SELECT export_byte_size, export_sha256
               FROM results_media_outputs
               WHERE workspace_id=? AND id=?
               FOR UPDATE""",
            (workspace_id, output_id),
        )).fetchone()
        if not row:
            return "not_found"
        if row[0] is not None or row[1] is not None:
            return "unchanged" if int(row[0]) == byte_size and str(row[1]) == sha256 else "conflict"
        await db.execute(
            """UPDATE results_media_outputs
               SET export_byte_size=?, export_sha256=?
               WHERE workspace_id=? AND id=?""",
            (byte_size, sha256, workspace_id, output_id),
        )
        await db.commit()
        return "recorded"


# ── Results Overlay Sessions ────────────────────────────────────────────────

async def get_station_session(workspace_id: str, station_id: str) -> dict[str, Any] | None:
    """Retrieve station results playback session."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            """SELECT
                workspace_id, station_id, media_output_id, state, cue_index,
                session_revision, controller_user_id, error_code, updated_at
            FROM results_overlay_sessions
            WHERE workspace_id = ? AND station_id = ?
            """,
            (workspace_id, station_id),
        )).fetchone()

        if not row:
            return None

        return {
            "workspace_id": str(row[0]),
            "station_id": str(row[1]),
            "media_output_id": str(row[2]) if row[2] else None,
            "state": str(row[3]),
            "cue_index": int(row[4]),
            "session_revision": int(row[5]),
            "controller_user_id": str(row[6]) if row[6] else None,
            "error_code": str(row[7]) if row[7] else None,
            "updated_at": str(row[8]),
        }


async def bind_station_session(
    workspace_id: str,
    station_id: str,
    media_output_id: str,
    expected_revision: int,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Bind a frozen live media output to station in ready state using CAS."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        if expected_revision == 0:
            row = await (await db.execute(
                """INSERT INTO results_overlay_sessions (
                    workspace_id, station_id, media_output_id, state, cue_index,
                    session_revision, controller_user_id, updated_at
                ) VALUES (?, ?, ?, 'ready', -1, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (workspace_id, station_id) DO NOTHING
                RETURNING workspace_id, station_id, media_output_id, state, cue_index,
                          session_revision, controller_user_id, error_code, updated_at
                """,
                (workspace_id, station_id, media_output_id, user_id),
            )).fetchone()
        else:
            row = await (await db.execute(
                """UPDATE results_overlay_sessions
                SET media_output_id = ?, state = 'ready', cue_index = -1,
                    session_revision = session_revision + 1, controller_user_id = ?,
                    error_code = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE workspace_id = ? AND station_id = ? AND session_revision = ?
                RETURNING workspace_id, station_id, media_output_id, state, cue_index,
                          session_revision, controller_user_id, error_code, updated_at
                """,
                (media_output_id, user_id, workspace_id, station_id, expected_revision),
            )).fetchone()

        if not row:
            return None

        await db.commit()

    return _row_to_session_dict(row)


async def update_station_session_command(
    workspace_id: str,
    station_id: str,
    new_state: str,
    new_cue_index: int,
    expected_revision: int,
    user_id: str | None = None,
    error_code: str | None = None,
) -> dict[str, Any] | None:
    """Apply an operator command to session with CAS on expected_revision."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            """UPDATE results_overlay_sessions
            SET state = ?, cue_index = ?, session_revision = session_revision + 1,
                controller_user_id = ?, error_code = ?, updated_at = CURRENT_TIMESTAMP
            WHERE workspace_id = ? AND station_id = ? AND session_revision = ?
            RETURNING workspace_id, station_id, media_output_id, state, cue_index,
                      session_revision, controller_user_id, error_code, updated_at
            """,
            (new_state, new_cue_index, user_id, error_code, workspace_id, station_id, expected_revision),
        )).fetchone()
        if not row:
            return None
        await db.commit()

    return _row_to_session_dict(row)


def _row_to_session_dict(row: Any) -> dict[str, Any]:
    return {
        "workspace_id": str(row[0]),
        "station_id": str(row[1]),
        "media_output_id": str(row[2]) if row[2] else None,
        "state": str(row[3]),
        "cue_index": int(row[4]),
        "session_revision": int(row[5]),
        "controller_user_id": str(row[6]) if row[6] else None,
        "error_code": str(row[7]) if row[7] else None,
        "updated_at": str(row[8]),
    }


# Aliases
create_result_version = create_result_version_with_entries
get_result_version = get_result_version_by_id
get_media_output_by_id = get_media_output
