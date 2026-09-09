"""Ownership-key migration preserves rows while allowing tenant collisions."""
from __future__ import annotations

import sqlite3

import aiosqlite
import pytest

from backend.core.schema_migrations import apply_sqlite_workspace_constraints


@pytest.mark.asyncio
async def test_legacy_link_and_overlay_keys_upgrade_without_losing_urls(tmp_path):
    path = tmp_path / "legacy-keys.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            PRAGMA foreign_keys=OFF;
            CREATE TABLE tournaments (slug TEXT PRIMARY KEY);
            CREATE TABLE players (discord_id TEXT PRIMARY KEY);
            CREATE TABLE tournament_player_links (
              tournament_slug TEXT NOT NULL, entrant_id TEXT NOT NULL,
              player_discord_id TEXT NOT NULL, workspace_id TEXT,
              created_at TEXT, PRIMARY KEY(tournament_slug, entrant_id)
            );
            CREATE TABLE overlays (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT UNIQUE, config TEXT, workspace_id TEXT);
            INSERT INTO tournaments VALUES ('cup');
            INSERT INTO players VALUES ('p1');
            INSERT INTO tournament_player_links VALUES ('cup','entrant-a','p1','ws-a','2026-01-01');
            INSERT INTO overlays(name,config,workspace_id) VALUES ('score','{"image":"/static/old.png"}','ws-a');
            """
        )
        db.commit()
    async with aiosqlite.connect(path) as db:
        await apply_sqlite_workspace_constraints(db)
        await db.commit()
        await db.execute("INSERT INTO tournament_player_links (tournament_slug,entrant_id,player_discord_id,workspace_id) VALUES ('cup','entrant-a','p1','ws-b')")
        await db.execute("INSERT INTO overlays(name,config,workspace_id) VALUES ('score','{}','ws-b')")
        await db.commit()
        links = await (await db.execute("SELECT workspace_id FROM tournament_player_links ORDER BY workspace_id")).fetchall()
        overlays = await (await db.execute("SELECT workspace_id,config FROM overlays ORDER BY workspace_id")).fetchall()
    assert [row[0] for row in links] == ["ws-a", "ws-b"]
    assert overlays[0][1] == '{"image":"/static/old.png"}'
    assert {row[0] for row in overlays} == {"ws-a", "ws-b"}


@pytest.mark.asyncio
async def test_constraint_upgrade_is_idempotent(tmp_path):
    path = tmp_path / "legacy-keys-idempotent.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE tournaments(slug TEXT PRIMARY KEY); CREATE TABLE players(discord_id TEXT PRIMARY KEY); CREATE TABLE tournament_player_links(tournament_slug TEXT, entrant_id TEXT, player_discord_id TEXT, workspace_id TEXT, PRIMARY KEY(tournament_slug, entrant_id)); CREATE TABLE overlays(id INTEGER PRIMARY KEY, name TEXT UNIQUE, config TEXT);")
        db.commit()
    async with aiosqlite.connect(path) as db:
        await apply_sqlite_workspace_constraints(db)
        await db.commit()
        await apply_sqlite_workspace_constraints(db)
        await db.commit()
        assert (await (await db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE '%__new'")).fetchone())[0] == 0
