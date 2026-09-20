"""Retention housekeeping removes only aged authentication artifacts."""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from pathlib import Path

from backend.core.storage import dbapi
import pytest

import backend.core.database as database
from backend.core.retention import purge_expired_auth_artifacts


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def retention_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "retention.pg"
    monkeypatch.setattr(database, "DATABASE_DSN", str(path))
    run(database.init_db())
    return path


def test_retention_purges_only_aged_auth_artifacts(retention_db: Path):
    async def verify():
        now = dt.datetime(2026, 9, 9, tzinfo=dt.timezone.utc)
        old = (now - dt.timedelta(days=31)).isoformat()
        future = (now + dt.timedelta(days=2)).isoformat()
        token_id = str(uuid.uuid4())
        async with dbapi.connect(retention_db) as db:
            before_workspaces = (await (await db.execute("SELECT COUNT(*) FROM workspaces")).fetchone())[0]
            user_id = str(uuid.uuid4())
            workspace_id = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO users (id,email,display_name,password_hash) VALUES (?,?,?,?)",
                (user_id, f"retention-{user_id}@example.test", "Retention", "hash"),
            )
            await db.execute(
                "INSERT INTO workspaces (id,slug,name) VALUES (?,?,?)",
                (workspace_id, f"retention-{workspace_id}", "Retention"),
            )
            await db.execute(
                "INSERT INTO workspace_memberships (workspace_id,user_id,role) VALUES (?,?,?)",
                (workspace_id, user_id, "owner"),
            )
            await db.execute(
                "INSERT INTO password_reset_tokens (id,user_id,token_hash,expires_at,used_at) VALUES (?,?,?,?,?)",
                (token_id, user_id, f"hash-{token_id}", old, old),
            )
            await db.execute(
                "INSERT INTO user_sessions (id,token_hash,user_id,workspace_id,expires_at,revoked_at) VALUES (?,?,?,?,?,?)",
                (str(uuid.uuid4()), f"session-old-{user_id}", user_id, workspace_id, future, old),
            )
            await db.execute(
                "INSERT INTO password_reset_tokens (id,user_id,token_hash,expires_at) VALUES (?,?,?,?)",
                (str(uuid.uuid4()), user_id, f"fresh-{token_id}", future),
            )
            await db.commit()

        counts = await purge_expired_auth_artifacts(now=now, retention_days=30)
        assert counts["password_reset_tokens"] == 1
        assert counts["user_sessions"] == 1
        async with dbapi.connect(retention_db) as db:
            reset_rows = await (await db.execute("SELECT COUNT(*) FROM password_reset_tokens")).fetchone()
            session_rows = await (await db.execute("SELECT COUNT(*) FROM user_sessions")).fetchone()
            workspace_rows = await (await db.execute("SELECT COUNT(*) FROM workspaces")).fetchone()
        assert reset_rows[0] == 1
        assert session_rows[0] == 0
        assert workspace_rows[0] == before_workspaces + 1

    run(verify())


def test_retention_rejects_unsafe_policy_without_writing(retention_db: Path):
    async def verify():
        async with dbapi.connect(retention_db) as db:
            before = (await (await db.execute("SELECT COUNT(*) FROM workspaces")).fetchone())[0]
        with pytest.raises(ValueError, match="safety range"):
            await purge_expired_auth_artifacts(retention_days=0)
        async with dbapi.connect(retention_db) as db:
            count = await (await db.execute("SELECT COUNT(*) FROM workspaces")).fetchone()
        # Invalid policy must leave all pre-existing workspace rows untouched.
        assert count[0] == before

    run(verify())
