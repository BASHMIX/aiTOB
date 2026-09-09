from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.backfill_legacy_workspace import backfill, inspect, owner_workspace


def _fixture_db(path: Path) -> tuple[str, str]:
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE workspaces (id TEXT PRIMARY KEY, created_at TEXT);
            CREATE TABLE workspace_memberships (workspace_id TEXT, user_id TEXT, role TEXT, status TEXT);
            CREATE TABLE tournaments (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE active_matches (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE players (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE stations (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE overlays (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE integration_accounts (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE integration_destinations (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE action_proposals (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE hub_commands (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE bot_feed (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE workflow_outbox (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE provider_command_ledger (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE provider_snapshot_cache (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE provider_api_budgets (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE dispatcher_decisions (id INTEGER PRIMARY KEY, workspace_id TEXT);
            CREATE TABLE dispatcher_dispatch_claims (id INTEGER PRIMARY KEY, workspace_id TEXT);
        """)
        db.execute("INSERT INTO workspaces VALUES ('owner', '2026-01-01')")
        db.execute("INSERT INTO workspace_memberships VALUES ('owner', 'user', 'owner', 'active')")
        db.execute("INSERT INTO tournaments VALUES (1, NULL)")
        db.execute("INSERT INTO active_matches VALUES (1, NULL)")
    return "owner", "other"


def test_backfill_is_atomic_idempotent_and_refuses_cross_workspace_rows(tmp_path: Path):
    path = tmp_path / "legacy.sqlite"
    owner, _ = _fixture_db(path)
    with sqlite3.connect(path) as db:
        assert owner_workspace(db, None) == owner
        assert dict(backfill(db, owner))["tournaments"] == 1
        db.commit()
        assert dict(backfill(db, owner))["tournaments"] == 0
        db.execute("INSERT INTO players VALUES (1, 'other')")
        with pytest.raises(RuntimeError, match="cross-workspace"):
            backfill(db, owner)
        db.rollback()
        assert inspect(db, owner)[0] == ("tournaments", 1, 0)
