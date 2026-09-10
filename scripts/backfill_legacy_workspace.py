"""Assign pre-workspace operational records to an explicit Owner workspace.

This is deliberately a SQLite-only migration tool.  Runtime code must never
use it or silently pick a workspace.  It supports a rehearsal against a copy
and performs all writes in one transaction when ``--apply`` is supplied.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


SCOPED_TABLES = (
    "tournaments", "active_matches", "players", "stations", "overlays",
    "integration_accounts", "integration_destinations", "action_proposals",
    "hub_commands", "workflow_outbox", "provider_command_ledger",
    "provider_snapshot_cache", "provider_api_budgets", "dispatcher_decisions",
    "dispatcher_dispatch_claims",
)

# ``bot_feed`` is intentionally absent: it is global operational telemetry,
# not a tenant-owned resource.  Assigning it to the Owner workspace would
# create a misleading ownership boundary for records that are not used by
# tournament, account, or worker decisions.


def owner_workspace(connection: sqlite3.Connection, requested: str | None) -> str:
    if requested:
        row = connection.execute(
            """SELECT w.id FROM workspaces w JOIN workspace_memberships m ON m.workspace_id=w.id
               WHERE w.id=? AND m.role='owner' AND m.status='active'""",
            (requested,),
        ).fetchone()
        if not row:
            raise RuntimeError("Requested workspace is not an active Owner workspace")
        return str(row[0])
    rows = connection.execute(
        """SELECT w.id FROM workspaces w JOIN workspace_memberships m ON m.workspace_id=w.id
           WHERE m.role='owner' AND m.status='active' ORDER BY w.created_at, w.id"""
    ).fetchall()
    if len(rows) != 1:
        raise RuntimeError("Exactly one active Owner workspace is required; pass --workspace-id explicitly if appropriate")
    return str(rows[0][0])


def table_has_workspace_id(connection: sqlite3.Connection, table: str) -> bool:
    return any(str(row[1]) == "workspace_id" for row in connection.execute(f"PRAGMA table_info({table})"))


def unscoped_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {table} WHERE workspace_id IS NULL").fetchone()[0])


def inspect(connection: sqlite3.Connection, workspace_id: str) -> list[tuple[str, int, int]]:
    report: list[tuple[str, int, int]] = []
    for table in SCOPED_TABLES:
        if not table_has_workspace_id(connection, table):
            raise RuntimeError(f"{table} has no workspace_id; run the additive schema migration first")
        total = int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        foreign = int(connection.execute(
            f"SELECT count(*) FROM {table} WHERE workspace_id IS NOT NULL AND workspace_id<>?", (workspace_id,)
        ).fetchone()[0])
        report.append((table, total, foreign))
    return report


def backfill(connection: sqlite3.Connection, workspace_id: str) -> dict[str, int]:
    report = inspect(connection, workspace_id)
    conflicts = [(table, foreign) for table, _total, foreign in report if foreign]
    if conflicts:
        details = ", ".join(f"{table}={count}" for table, count in conflicts)
        raise RuntimeError(f"Refusing cross-workspace reassignment: {details}")
    changed: dict[str, int] = {}
    for table, _total, _foreign in report:
        cur = connection.execute(f"UPDATE {table} SET workspace_id=? WHERE workspace_id IS NULL", (workspace_id,))
        changed[table] = int(cur.rowcount)
    # The early integration prototype used the literal owner_id='admin'.  It
    # was not an authenticated user ID.  Once the designated Owner workspace
    # exists, normalize this legacy ownership marker so account list queries
    # cannot retain a hidden global fallback.
    account_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(integration_accounts)")}
    if {"workspace_id", "owner_id"}.issubset(account_columns):
        cur = connection.execute(
            "UPDATE integration_accounts SET owner_id=? WHERE workspace_id=? AND owner_id IN ('admin', 'default')",
            (workspace_id, workspace_id),
        )
        changed["integration_account_owner_normalized"] = int(cur.rowcount)
    app_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(integration_oauth_applications)")}
    if "owner_id" in app_columns:
        cur = connection.execute(
            "UPDATE integration_oauth_applications SET owner_id=? WHERE owner_id IN ('admin', 'default')",
            (workspace_id,),
        )
        changed["oauth_application_owner_normalized"] = int(cur.rowcount)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--workspace-id")
    parser.add_argument("--apply", action="store_true", help="write the scoped ownership backfill")
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit("Database file does not exist")
    with sqlite3.connect(args.database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        workspace_id = owner_workspace(connection, args.workspace_id)
        before = inspect(connection, workspace_id)
        if not args.apply:
            for table, total, foreign in before:
                unscoped = unscoped_count(connection, table)
                print(f"{table}: total={total} eligible_unscoped={unscoped} foreign={foreign}")
            print("Dry run only; no data was changed.")
            return 0
        connection.execute("BEGIN IMMEDIATE")
        try:
            changed = backfill(connection, workspace_id)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    print("Applied ownership backfill: " + ", ".join(f"{table}={count}" for table, count in changed.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
