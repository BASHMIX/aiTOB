"""Revocable, least-privilege Browser Source access."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from backend.core import database
from backend.core.storage import dbapi as aiosqlite
from backend.core.timestamps import as_utc


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_overlay_access(workspace_id: str, station_public_id: str, actor_id: str) -> tuple[str, str]:
    station = await database.get_station(station_public_id, workspace_id)
    if not station:
        raise ValueError("Station not found in workspace")
    token = secrets.token_urlsafe(36)
    token_id = str(uuid.uuid4())
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            "UPDATE overlay_access_tokens SET revoked_at=CURRENT_TIMESTAMP WHERE workspace_id=? AND station_id=? AND revoked_at IS NULL",
            (workspace_id, station["storage_id"]),
        )
        await db.execute(
            """INSERT INTO overlay_access_tokens
               (id, workspace_id, station_id, token_hash, created_by) VALUES (?, ?, ?, ?, ?)""",
            (token_id, workspace_id, station["storage_id"], _hash(token), actor_id),
        )
        await db.commit()
    return token_id, token


async def resolve_overlay_access(token: str, station_public_id: str) -> dict | None:
    if not token:
        return None
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            """SELECT oat.id, oat.workspace_id, oat.station_id, oat.expires_at,
                      s.public_id, s.name, s.active_overlay
               FROM overlay_access_tokens oat JOIN stations s ON s.id=oat.station_id
               WHERE oat.token_hash=? AND oat.revoked_at IS NULL
                 AND (s.public_id=? OR s.id=?)""",
            (_hash(token), station_public_id, station_public_id),
        )).fetchone()
    if not row:
        return None
    result = dict(row)
    if result.get("expires_at") and as_utc(result["expires_at"]) <= datetime.now(UTC):
        return None
    return result


async def revoke_overlay_access(workspace_id: str, token_id: str) -> bool:
    async with aiosqlite.connect(database.DB_PATH) as db:
        result = await db.execute(
            "UPDATE overlay_access_tokens SET revoked_at=CURRENT_TIMESTAMP WHERE id=? AND workspace_id=? AND revoked_at IS NULL",
            (token_id, workspace_id),
        )
        await db.commit()
    return result.rowcount == 1
