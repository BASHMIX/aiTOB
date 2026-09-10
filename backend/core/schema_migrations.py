"""Transactional, serialized PostgreSQL schema upgrades with durable receipts.

The existing additive schema definitions remain authoritative. Each converted
statement has a content-addressed receipt; no successful DDL is silently retried.
This does not repair or reinterpret user data.
"""
from __future__ import annotations

import hashlib
import os

from backend.core.database_schema import INDEXES, MIGRATIONS, TABLE_SCHEMAS
from backend.core.storage import postgres_ddl


async def apply_sqlite_workspace_constraints(db):
    """Rebuild legacy SQLite tables with workspace-aware keys in one transaction.

    This function is intentionally called only by migration/rehearsal tooling;
    runtime services must use PostgreSQL. Existing rows and image/config URLs
    are copied verbatim and no status or workflow fields are interpreted.
    """
    async def indexes(table: str):
        async with db.execute(f"PRAGMA index_list('{table}')") as cursor:
            result = []
            for row in await cursor.fetchall():
                # seq, name, unique, origin, partial
                if not row[2]:
                    continue
                async with db.execute(f"PRAGMA index_info('{row[1]}')") as info:
                    result.append([item[2] for item in await info.fetchall()])
            return result

    link_cols = {row[1] for row in await (await db.execute("PRAGMA table_info(tournament_player_links)")).fetchall()}
    link_indexes = await indexes("tournament_player_links")
    if "id" not in link_cols or ["workspace_id", "tournament_slug", "entrant_id"] not in link_indexes:
        await db.execute("""CREATE TABLE tournament_player_links__new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_slug TEXT NOT NULL, entrant_id TEXT NOT NULL,
            player_discord_id TEXT NOT NULL, workspace_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(workspace_id, tournament_slug, entrant_id),
            FOREIGN KEY(tournament_slug) REFERENCES tournaments(slug),
            FOREIGN KEY(player_discord_id) REFERENCES players(discord_id)
        )""")
        cols = ["tournament_slug", "entrant_id", "player_discord_id", "workspace_id", "created_at"]
        cols = [column for column in cols if column in link_cols]
        await db.execute(
            "INSERT INTO tournament_player_links__new (" + ",".join(cols) + ") "
            "SELECT " + ",".join(cols) + " FROM tournament_player_links"
        )
        await db.execute("DROP TABLE tournament_player_links")
        await db.execute("ALTER TABLE tournament_player_links__new RENAME TO tournament_player_links")

    overlay_cols = {row[1] for row in await (await db.execute("PRAGMA table_info(overlays)")).fetchall()}
    overlay_indexes = await indexes("overlays")
    if "workspace_id" not in overlay_cols or ["workspace_id", "name"] not in overlay_indexes:
        await db.execute("""CREATE TABLE overlays__new (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            config TEXT, workspace_id TEXT, UNIQUE(workspace_id, name)
        )""")
        cols = ["id", "name", "config", "workspace_id"]
        available = [column for column in cols if column in overlay_cols]
        select_cols = ",".join(available)
        await db.execute(
            "INSERT INTO overlays__new (" + select_cols + ") SELECT " + select_cols + " FROM overlays"
        )
        await db.execute("DROP TABLE overlays")
        await db.execute("ALTER TABLE overlays__new RENAME TO overlays")


def migration_statements():
    for phase, statements in (("table", TABLE_SCHEMAS), ("addition", MIGRATIONS), ("index", INDEXES)):
        for statement in statements:
            converted = postgres_ddl(statement)
            digest = hashlib.sha256(converted.encode()).hexdigest()
            yield f"{phase}:{digest}", phase, converted


async def apply_postgres_schema(db):
    # API and bot can start together. Serialize before creating the receipt
    # table: PostgreSQL CREATE TABLE IF NOT EXISTS alone can still race.
    await db.execute("SELECT pg_advisory_xact_lock(734102902)")
    await db.execute("""CREATE TABLE IF NOT EXISTS schema_migration_history (
        migration_id TEXT PRIMARY KEY,
        phase TEXT NOT NULL,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    for migration_id, phase, statement in migration_statements():
        existing = await (await db.execute(
            "SELECT 1 FROM schema_migration_history WHERE migration_id=?", (migration_id,)
        )).fetchone()
        if existing:
            continue
        await db.execute(statement)
        await db.execute("INSERT INTO schema_migration_history (migration_id, phase) VALUES (?, ?)", (migration_id, phase))
    await apply_workspace_constraint_migrations(db)
    if os.getenv("AITOB_ENFORCE_WORKSPACE_NOT_NULL", "").strip().lower() in {"1", "true", "yes"}:
        await enforce_postgres_workspace_ownership(db)
    # Caller commits the schema and its receipts in the same transaction.


POSTGRES_WORKSPACE_TABLES = (
    "action_proposals", "active_matches", "ai_usage_ledger", "audit_events",
    "dispatcher_decisions", "dispatcher_dispatch_claims", "hub_commands",
    "integration_accounts", "integration_destinations", "media_assets",
    "overlay_access_tokens", "overlays", "planned_streams", "player_overrides",
    "players", "provider_api_budgets", "provider_api_usage",
    "provider_command_ledger", "provider_identity_links",
    "provider_snapshot_cache", "stations", "tournament_player_links",
    "tournaments", "user_sessions", "workflow_outbox",
    "workspace_entitlements", "workspace_invitations", "workspace_memberships",
)


async def enforce_postgres_workspace_ownership(db):
    """Make the candidate's operational ownership backfill durable.

    This gate is opt-in because legacy databases must be backfilled and
    reviewed first. It never assigns a workspace; any remaining NULL row fails
    startup before the transaction commits. Global telemetry tables are
    intentionally excluded and remain outside tenant projections.
    """
    for table in POSTGRES_WORKSPACE_TABLES:
        async with db.execute(
            f"SELECT count(*) FROM {table} WHERE workspace_id IS NULL"
        ) as cursor:
            row = await cursor.fetchone()
        if row and int(row[0]) > 0:
            raise RuntimeError(
                f"workspace ownership backfill required before enforcing {table}"
            )
        await db.execute(
            f"ALTER TABLE {table} ALTER COLUMN workspace_id SET NOT NULL"
        )


async def apply_workspace_constraint_migrations(db):
    """Upgrade legacy global keys without rewriting any row values.

    Older installations used ``overlays.name`` and
    ``tournament_player_links(tournament_slug, entrant_id)`` as global keys.
    The upgrade adds a durable link id and workspace-aware unique indexes so
    two organizations may safely use the same provider identifiers or overlay
    names. It is idempotent and runs inside the caller's schema transaction.
    """
    await db.execute(
        "ALTER TABLE tournament_player_links ADD COLUMN IF NOT EXISTS id BIGINT GENERATED BY DEFAULT AS IDENTITY"
    )
    await db.execute("UPDATE tournament_player_links SET id = DEFAULT WHERE id IS NULL")
    async with db.execute(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'tournament_player_links'::regclass AND contype = 'p'"
    ) as cursor:
        link_pk = await cursor.fetchall()
    legacy_link_pk = False
    for row in link_pk:
        definition = str(row[1]).lower().replace(' ', '')
        if 'tournament_slug,entrant_id' in definition:
            legacy_link_pk = True
            await db.execute(f'ALTER TABLE tournament_player_links DROP CONSTRAINT "{row[0]}"')
    async with db.execute(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'overlays'::regclass AND contype = 'u'"
    ) as cursor:
        overlay_uniques = await cursor.fetchall()
    for row in overlay_uniques:
        definition = str(row[1]).lower().replace(' ', '')
        if definition in ('unique(name)', 'unique(name)deferrable'):
            await db.execute(f'ALTER TABLE overlays DROP CONSTRAINT "{row[0]}"')
    if legacy_link_pk:
        await db.execute(
            "ALTER TABLE tournament_player_links ADD CONSTRAINT tournament_player_links_pkey "
            "PRIMARY KEY (id)"
        )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tournament_player_links_workspace "
        "ON tournament_player_links (workspace_id, tournament_slug, entrant_id)"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_overlays_workspace_name "
        "ON overlays (workspace_id, name)"
    )
