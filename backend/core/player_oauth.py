"""Single-use, workspace-owned OAuth routing for Discord player registration."""

from __future__ import annotations

import hashlib
import secrets
import time

from backend.core import database
from backend.core.storage import dbapi


_PROVIDER = "startgg-player"
_RETURN_STEP = "discord-registration"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def create_player_oauth_state(
    workspace_id: str,
    discord_id: str,
    *,
    ttl_seconds: int = 600,
) -> str:
    """Create an opaque state whose routing context never enters the URL."""

    workspace = str(workspace_id or "").strip()
    actor = str(discord_id or "").strip()
    if not workspace or not actor:
        raise ValueError("Player OAuth state requires workspace and Discord user IDs")
    opaque = secrets.token_urlsafe(32)
    now = int(time.time())
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "DELETE FROM provider_oauth_states WHERE provider=? AND expires_at<=?",
            (_PROVIDER, now),
        )
        await db.execute(
            """INSERT INTO provider_oauth_states (
                   state_hash, provider, workspace_id, actor_id, return_step, expires_at
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (_hash(opaque), _PROVIDER, workspace, actor, _RETURN_STEP, now + ttl_seconds),
        )
        await db.commit()
    return opaque


async def inspect_player_oauth_state(state: str) -> dict[str, str] | None:
    """Validate a state before redirecting without consuming the callback nonce."""

    opaque = str(state or "").strip()
    if not opaque:
        return None
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        row = await (await db.execute(
            """SELECT workspace_id, actor_id
                 FROM provider_oauth_states
                WHERE state_hash=? AND provider=? AND expires_at>?""",
            (_hash(opaque), _PROVIDER, int(time.time())),
        )).fetchone()
    return dict(row) if row else None


async def consume_player_oauth_state(state: str) -> dict[str, str] | None:
    """Atomically consume one valid state and return its trusted route."""

    opaque = str(state or "").strip()
    if not opaque:
        return None
    now = int(time.time())
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        row = await (await db.execute(
            """DELETE FROM provider_oauth_states
                WHERE state_hash=? AND provider=? AND expires_at>?
                RETURNING workspace_id, actor_id""",
            (_hash(opaque), _PROVIDER, now),
        )).fetchone()
        await db.execute(
            "DELETE FROM provider_oauth_states WHERE provider=? AND expires_at<=?",
            (_PROVIDER, now),
        )
        await db.commit()
    return dict(row) if row else None


__all__ = [
    "create_player_oauth_state",
    "inspect_player_oauth_state",
    "consume_player_oauth_state",
]
