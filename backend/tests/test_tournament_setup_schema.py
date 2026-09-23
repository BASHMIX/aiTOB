"""PostgreSQL schema contracts for Tournament Setup aggregates.

These tests describe the PostgreSQL storage boundary required by feature 004,
including foreign keys, partial unique indexes, and workspace ownership.
"""

from __future__ import annotations

import pytest

from backend.core import database


# Every new operational aggregate has a direct workspace owner.  Credentials
# are the intentional exception: they are owned by an integration account and
# inherit workspace ownership through that account's FK.
WORKSPACE_OWNED_TABLES = (
    "tournament_setup_drafts",
    "integration_accounts",
    "integration_connection_health",
    "workspace_ai_configs",
    "ai_usage_ledger",
    "provider_scope_bindings",
    "match_call_occurrences",
    "tournament_brands",
    "tournament_operating_profiles",
    "tournament_discord_bindings",
    "tournament_registration_configs",
    "tournament_player_enrollments",
    "player_identity_verification_challenges",
    "provider_roster_snapshots",
    "bot_experience_profiles",
    "tournament_setup_templates",
    "tournament_readiness_snapshots",
)


# These are the cross-aggregate ownership edges which prevent a child from
# being attached to a resource in another workspace.  The implementation may
# enforce an edge with a composite FK; the source/target column pair remains
# visible in PostgreSQL's constraint catalog either way.
REQUIRED_FOREIGN_KEYS = (
    ("tournament_setup_drafts", "workspace_id", "workspaces", "id"),
    ("tournament_setup_drafts", "created_by", "users", "id"),
    ("tournament_setup_drafts", "updated_by", "users", "id"),
    ("tournament_setup_drafts", "provider_account_id", "integration_accounts", "id"),
    ("tournament_setup_drafts", "discord_account_id", "integration_accounts", "id"),
    ("tournament_setup_drafts", "ai_account_id", "integration_accounts", "id"),
    ("tournament_setup_drafts", "logo_asset_id", "media_assets", "id"),
    ("tournament_setup_drafts", "materialized_tournament_id", "tournaments", "id"),
    ("integration_accounts", "workspace_id", "workspaces", "id"),
    ("integration_connection_health", "account_id", "integration_accounts", "id"),
    ("integration_connection_health", "workspace_id", "workspaces", "id"),
    ("workspace_ai_configs", "workspace_id", "workspaces", "id"),
    ("workspace_ai_configs", "selected_account_id", "integration_accounts", "id"),
    ("ai_usage_ledger", "workspace_id", "workspaces", "id"),
    ("ai_usage_ledger", "tournament_id", "tournaments", "id"),
    ("ai_usage_ledger", "integration_account_id", "integration_accounts", "id"),
    ("provider_scope_bindings", "tournament_id", "tournaments", "id"),
    ("provider_scope_bindings", "workspace_id", "workspaces", "id"),
    ("provider_scope_bindings", "provider_account_id", "integration_accounts", "id"),
    ("match_call_occurrences", "tournament_id", "tournaments", "id"),
    ("match_call_occurrences", "workspace_id", "workspaces", "id"),
    ("tournament_brands", "tournament_id", "tournaments", "id"),
    ("tournament_brands", "workspace_id", "workspaces", "id"),
    ("tournament_brands", "logo_asset_id", "media_assets", "id"),
    ("tournament_operating_profiles", "tournament_id", "tournaments", "id"),
    ("tournament_operating_profiles", "workspace_id", "workspaces", "id"),
    ("tournament_discord_bindings", "tournament_id", "tournaments", "id"),
    ("tournament_discord_bindings", "workspace_id", "workspaces", "id"),
    ("tournament_discord_bindings", "discord_account_id", "integration_accounts", "id"),
    ("tournament_discord_bindings", "match_destination_id", "integration_destinations", "id"),
    ("tournament_discord_bindings", "escalation_destination_id", "integration_destinations", "id"),
    ("tournament_registration_configs", "tournament_id", "tournaments", "id"),
    ("tournament_registration_configs", "workspace_id", "workspaces", "id"),
    ("tournament_player_enrollments", "tournament_id", "tournaments", "id"),
    ("tournament_player_enrollments", "workspace_id", "workspaces", "id"),
    ("tournament_player_enrollments", "player_profile_id", "player_profiles", "id"),
    ("tournament_player_enrollments", "player_identity_id", "player_identities", "id"),
    ("tournament_player_enrollments", "provider_identity_link_id", "provider_identity_links", "id"),
    ("tournament_player_enrollments", "roster_snapshot_id", "provider_roster_snapshots", "id"),
    ("tournament_player_enrollments", "image_asset_id", "media_assets", "id"),
    ("player_identity_verification_challenges", "workspace_id", "workspaces", "id"),
    ("player_identity_verification_challenges", "tournament_id", "tournaments", "id"),
    ("player_identity_verification_challenges", "enrollment_id", "tournament_player_enrollments", "id"),
    ("provider_roster_snapshots", "workspace_id", "workspaces", "id"),
    ("provider_roster_snapshots", "tournament_id", "tournaments", "id"),
    ("provider_roster_snapshots", "provider_account_id", "integration_accounts", "id"),
    ("bot_experience_profiles", "workspace_id", "workspaces", "id"),
    ("bot_experience_profiles", "tournament_id", "tournaments", "id"),
    ("bot_experience_profiles", "guild_avatar_asset_id", "media_assets", "id"),
    ("bot_experience_profiles", "guild_banner_asset_id", "media_assets", "id"),
    ("tournament_setup_templates", "workspace_id", "workspaces", "id"),
    ("tournament_setup_templates", "created_by", "users", "id"),
    ("tournament_setup_templates", "updated_by", "users", "id"),
    ("tournament_readiness_snapshots", "workspace_id", "workspaces", "id"),
    ("tournament_readiness_snapshots", "draft_id", "tournament_setup_drafts", "id"),
    ("tournament_readiness_snapshots", "tournament_id", "tournaments", "id"),
)


# Explicit business keys from data-model.md.  UUID primary keys may remain
# globally unique; these keys are the boundaries where two workspaces must be
# allowed to use the same external identity or display value independently.
REQUIRED_SCOPED_UNIQUES = (
    ("integration_accounts", ("workspace_id", "provider_type", "external_account_id")),
    ("provider_scope_bindings", ("workspace_id", "provider_account_id", "provider_type", "external_scope_id")),
    ("match_call_occurrences", ("workspace_id", "tournament_id", "match_id", "occurrence_version")),
    ("tournament_setup_templates", ("workspace_id", "name")),
    ("tournament_player_enrollments", ("workspace_id", "tournament_id", "discord_user_id")),
    ("tournament_player_enrollments", ("workspace_id", "tournament_id", "provider_entrant_id")),
)


async def _rows(statement: str, parameters: tuple = ()) -> list:
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(statement, parameters) as cursor:
            return await cursor.fetchall()


async def _columns_for(table: str) -> dict[str, str]:
    rows = await _rows(
        """
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ?
        """,
        (table,),
    )
    return {row["column_name"]: row["is_nullable"] for row in rows}


async def _foreign_keys() -> set[tuple[str, str, str, str]]:
    rows = await _rows(
        """
        SELECT source_rel.relname AS source_table,
               source_attr.attname AS source_column,
               target_rel.relname AS target_table,
               target_attr.attname AS target_column
        FROM pg_constraint AS constraint_row
        JOIN pg_class AS source_rel
          ON source_rel.oid = constraint_row.conrelid
        JOIN pg_namespace AS source_schema
          ON source_schema.oid = source_rel.relnamespace
        JOIN pg_class AS target_rel
          ON target_rel.oid = constraint_row.confrelid
        JOIN LATERAL unnest(constraint_row.conkey)
          WITH ORDINALITY AS source_key(attnum, position) ON TRUE
        JOIN pg_attribute AS source_attr
          ON source_attr.attrelid = source_rel.oid
         AND source_attr.attnum = source_key.attnum
        JOIN LATERAL unnest(constraint_row.confkey)
          WITH ORDINALITY AS target_key(attnum, position)
          ON target_key.position = source_key.position
        JOIN pg_attribute AS target_attr
          ON target_attr.attrelid = target_rel.oid
         AND target_attr.attnum = target_key.attnum
        WHERE constraint_row.contype = 'f'
          AND source_schema.nspname = 'public'
        """
    )
    return {
        (
            row["source_table"],
            row["source_column"],
            row["target_table"],
            row["target_column"],
        )
        for row in rows
    }


async def _unique_indexes(table: str) -> set[tuple[str, ...]]:
    rows = await _rows(
        """
        SELECT array_agg(attribute.attname ORDER BY index_key.position) AS columns
        FROM pg_index AS index_row
        JOIN pg_class AS table_row
          ON table_row.oid = index_row.indrelid
        JOIN pg_class AS index_name
          ON index_name.oid = index_row.indexrelid
        JOIN pg_namespace AS table_schema
          ON table_schema.oid = table_row.relnamespace
        JOIN LATERAL unnest(index_row.indkey)
          WITH ORDINALITY AS index_key(attnum, position) ON TRUE
        JOIN pg_attribute AS attribute
          ON attribute.attrelid = table_row.oid
         AND attribute.attnum = index_key.attnum
        WHERE index_row.indisunique
          AND table_schema.nspname = 'public'
          AND table_row.relname = ?
        GROUP BY index_name.oid
        """,
        (table,),
    )
    return {tuple(row["columns"]) for row in rows}


@pytest.mark.asyncio
async def test_every_new_aggregate_has_non_null_workspace_ownership():
    """No wizard aggregate may admit an unowned operational row."""
    missing_tables: list[str] = []
    missing_workspace_columns: list[str] = []
    nullable_workspace_columns: list[str] = []

    for table in WORKSPACE_OWNED_TABLES:
        columns = await _columns_for(table)
        if not columns:
            missing_tables.append(table)
            continue
        if "workspace_id" not in columns:
            missing_workspace_columns.append(table)
        elif columns["workspace_id"] != "NO":
            nullable_workspace_columns.append(table)

    assert not missing_tables, f"missing Tournament Setup tables: {missing_tables}"
    assert not missing_workspace_columns, (
        f"workspace ownership column missing from: {missing_workspace_columns}"
    )
    assert not nullable_workspace_columns, (
        f"workspace_id must be NOT NULL for: {nullable_workspace_columns}"
    )


@pytest.mark.asyncio
async def test_workspace_and_child_foreign_keys_are_declared():
    """Every cross-aggregate reference must be database-enforced."""
    foreign_keys = await _foreign_keys()
    missing = [edge for edge in REQUIRED_FOREIGN_KEYS if edge not in foreign_keys]
    assert not missing, f"missing required foreign keys: {missing}"


@pytest.mark.asyncio
async def test_business_uniqueness_is_scoped_to_workspace():
    """External identities and player claims cannot collide across one workspace."""
    missing: list[tuple[str, tuple[str, ...]]] = []
    for table, columns in REQUIRED_SCOPED_UNIQUES:
        if columns not in await _unique_indexes(table):
            missing.append((table, columns))
    assert not missing, f"missing workspace-scoped unique constraints: {missing}"


@pytest.mark.asyncio
async def test_workspace_scoping_has_no_global_business_key_indexes():
    """A global business-key index would reintroduce cross-workspace leakage."""
    forbidden_global_keys = {
        ("integration_accounts", ("provider_type", "external_account_id")),
        ("provider_scope_bindings", ("provider_account_id", "provider_type", "external_scope_id")),
        ("match_call_occurrences", ("tournament_id", "match_id", "occurrence_version")),
        ("tournament_setup_templates", ("name",)),
        ("tournament_player_enrollments", ("tournament_id", "discord_user_id")),
        ("tournament_player_enrollments", ("tournament_id", "provider_entrant_id")),
    }

    violations: list[tuple[str, tuple[str, ...]]] = []
    for table, global_columns in forbidden_global_keys:
        indexes = await _unique_indexes(table)
        if global_columns in indexes:
            violations.append((table, global_columns))
    assert not violations, f"global unique business keys bypass workspace isolation: {violations}"
