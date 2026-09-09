"""End-to-end read-only SQLite to disposable PostgreSQL migration acceptance."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import uuid
import hashlib
from urllib.parse import urlsplit, urlunsplit

import pytest

from backend.core import database


PG_TEST_URL = os.getenv("AITOB_PG_TEST_URL")
pytestmark = pytest.mark.skipif(not PG_TEST_URL, reason="requires explicit AITOB_PG_TEST_URL")


@pytest.mark.asyncio
async def test_readonly_sqlite_migration_preserves_workspace_ownership_and_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import psycopg
    from psycopg import sql

    source = tmp_path / "migration-source.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(source))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_EMAIL", "migrated-owner@example.test")
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", "migration-owner-password")
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_NAME", "Migrated owner")
    monkeypatch.setenv("AITOB_BOOTSTRAP_WORKSPACE_NAME", "Migrated workspace")
    await database.init_db()
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        workspace = await (await db.execute("SELECT id FROM workspaces")).fetchone()
        await db.execute("INSERT INTO players (discord_id, avatar_path, workspace_id) VALUES ('player', '/static/avatars/legacy.png', ?)", (workspace[0],))
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES ('workspace-b', 'workspace-b', 'Workspace B')")
        await db.execute("INSERT INTO tournaments (slug, name, workspace_id) VALUES ('legacy/tournament', 'Legacy', ?)", (workspace[0],))
        await db.execute("INSERT INTO tournaments (slug, name, workspace_id) VALUES ('legacy/tournament-b', 'Legacy B', ?)", ('workspace-b',))
        await db.execute(
            "INSERT INTO active_matches (set_id, tournament_slug, workspace_id, match_number) VALUES ('legacy-set', 'legacy/tournament', ?, 'R-1')",
            (workspace[0],),
        )
        await db.execute("INSERT INTO tournament_player_links (tournament_slug, entrant_id, player_discord_id, workspace_id) VALUES ('legacy/tournament','entrant-a','player',?)", (workspace[0],))
        await db.execute("INSERT INTO tournament_player_links (tournament_slug, entrant_id, player_discord_id, workspace_id) VALUES ('legacy/tournament-b','entrant-a','player',?)", ('workspace-b',))
        await db.execute("INSERT INTO overlays (name, config, workspace_id) VALUES ('shared-overlay','{\"image\":\"/static/legacy.png\"}',?)", (workspace[0],))
        await db.execute("INSERT INTO overlays (name, config, workspace_id) VALUES ('shared-overlay','{}',?)", ('workspace-b',))
        await db.commit()

    assert source.exists()
    original_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    parts = urlsplit(PG_TEST_URL or "")
    name = "aitob_migration_" + uuid.uuid4().hex[:16]
    target = urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))
    admin = urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment))
    with psycopg.connect(admin, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "scripts/migrate_sqlite_to_postgres.py", "--source", str(source)],
            env={**os.environ, "DATABASE_URL": target}, timeout=90,
            cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original_digest
        with psycopg.connect(target) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM tournaments WHERE workspace_id IS NULL")
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT avatar_path FROM players WHERE discord_id='player'")
            assert cur.fetchone()[0] == "/static/avatars/legacy.png"
            cur.execute("SELECT match_number FROM active_matches WHERE set_id='legacy-set'")
            assert cur.fetchone()[0] == "R-1"
            cur.execute("SELECT count(*) FROM app_migrations WHERE name='sqlite-to-postgres-v1'")
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT count(*) FROM tournament_player_links WHERE entrant_id='entrant-a'")
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT count(*) FROM overlays WHERE name='shared-overlay'")
            assert cur.fetchone()[0] == 2
    finally:
        with psycopg.connect(admin, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
