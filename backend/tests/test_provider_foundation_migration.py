"""Phase-2 upgrade tests against a representative pre-V2 SQLite database."""
from __future__ import annotations

import sqlite3

import aiosqlite
import pytest

from backend.core import database


def _create_pre_v2_database(path: str) -> None:
    """Create the relevant shape from a persisted legacy Start.gg installation."""
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE tournaments (
                slug TEXT PRIMARY KEY, name TEXT, event_name TEXT, event_id TEXT,
                game TEXT, stream_slot TEXT, raw_data TEXT
            );
            CREATE TABLE stations (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, hidden BOOLEAN DEFAULT FALSE
            );
            CREATE TABLE active_matches (
                set_id TEXT PRIMARY KEY, tournament_slug TEXT, station_id TEXT,
                p1_name TEXT, p1_score INTEGER DEFAULT 0, p2_name TEXT,
                p2_score INTEGER DEFAULT 0, p1_entrant_id TEXT, p2_entrant_id TEXT,
                p1_discord TEXT, p2_discord TEXT, round_name TEXT, match_number INTEGER,
                swapped BOOLEAN DEFAULT FALSE, bot_enabled BOOLEAN DEFAULT TRUE,
                status TEXT DEFAULT 'not_started', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        db.execute("INSERT INTO tournaments (slug, name) VALUES ('legacy-startgg', 'Legacy Start.gg')")
        db.execute(
            "INSERT INTO stations (id, name) VALUES ('station_legacy', 'Legacy stream station')"
        )
        db.execute(
            """INSERT INTO active_matches (
                set_id, tournament_slug, station_id, p1_name, p2_name,
                p1_entrant_id, p2_entrant_id, p1_discord, p2_discord, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "set-legacy", "legacy-startgg", "station_legacy", "Player One", "Player Two",
                "entrant-1", "entrant-2", "discord-1", "discord-2", "in_progress",
            ),
        )
        # This field existed before V2 and must survive the additive migrations.
        db.execute("ALTER TABLE stations ADD COLUMN startgg_stream_id TEXT")
        db.execute("UPDATE stations SET startgg_stream_id = 'stream-legacy'")
        db.execute("ALTER TABLE active_matches ADD COLUMN discord_thread_id TEXT")
        db.execute("UPDATE active_matches SET discord_thread_id = 'thread-legacy'")
        db.commit()


@pytest.mark.asyncio
async def test_v2_migration_adds_storage_without_reinterpreting_legacy_startgg_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.sqlite"
    _create_pre_v2_database(str(db_path))
    monkeypatch.setattr(database, "DB_PATH", str(db_path))

    await database.init_db()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM active_matches WHERE set_id = 'set-legacy'") as cursor:
            legacy_match = dict(await cursor.fetchone())
        async with db.execute("SELECT * FROM stations WHERE id = 'station_legacy'") as cursor:
            station = dict(await cursor.fetchone())
        async with db.execute("SELECT name FROM sqlite_master WHERE type = 'table'") as cursor:
            tables = {row[0] for row in await cursor.fetchall()}

    assert legacy_match["status"] == "in_progress"
    assert legacy_match["station_id"] == "station_legacy"
    assert legacy_match["p1_discord"] == "discord-1"
    assert legacy_match["p2_discord"] == "discord-2"
    assert legacy_match["discord_thread_id"] == "thread-legacy"
    assert legacy_match["provider_state_raw"] is None
    assert legacy_match["hub_status"] is None
    assert legacy_match["sync_status"] is None
    assert station["startgg_stream_id"] == "stream-legacy"
    assert {
        "provider_command_ledger", "workflow_outbox", "provider_reconciliation_audit",
        "provider_identity_links", "provider_api_budgets", "provider_snapshot_cache",
    }.issubset(tables)

