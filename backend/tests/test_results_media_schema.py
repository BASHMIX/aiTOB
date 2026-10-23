"""PostgreSQL schema and constraint tests for Tournament Results Media."""

from __future__ import annotations

import pytest
from backend.core import database
from backend.core.schema_migrations import POSTGRES_WORKSPACE_TABLES


RESULTS_MEDIA_TABLES = (
    "tournament_result_versions",
    "tournament_result_entries",
    "results_media_outputs",
    "results_overlay_sessions",
)


@pytest.mark.asyncio
async def test_results_media_tables_exist(postgres_repository_database):
    """Verify all 4 Results Media tables exist in PostgreSQL."""
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        res = await (await db.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(?)
            """,
            (list(RESULTS_MEDIA_TABLES),),
        )).fetchall()
        found_tables = {row[0] for row in res}
        missing = set(RESULTS_MEDIA_TABLES) - found_tables
        assert not missing, f"Missing tables in PostgreSQL schema: {missing}"


def test_results_media_tables_registered_in_workspace_tables():
    """Verify all Results Media tables are declared in POSTGRES_WORKSPACE_TABLES."""
    for table in RESULTS_MEDIA_TABLES:
        assert table in POSTGRES_WORKSPACE_TABLES, f"{table} missing from POSTGRES_WORKSPACE_TABLES"


@pytest.mark.asyncio
async def test_results_media_foreign_keys_and_constraints(postgres_repository_database):
    """Verify check constraints and foreign keys for Results Media tables."""
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        # Check foreign keys
        fk_rows = await (await db.execute(
            """
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = ANY(?)
            """,
            (list(RESULTS_MEDIA_TABLES),),
        )).fetchall()

        fks = {(row[0], row[1], row[2], row[3]) for row in fk_rows}

        expected_fks = {
            ("tournament_result_versions", "workspace_id", "workspaces", "id"),
            ("tournament_result_versions", "created_by", "users", "id"),
            ("tournament_result_entries", "version_id", "tournament_result_versions", "id"),
            ("tournament_result_entries", "workspace_id", "workspaces", "id"),
            ("results_media_outputs", "workspace_id", "workspaces", "id"),
            ("results_media_outputs", "result_version_id", "tournament_result_versions", "id"),
            ("results_media_outputs", "created_by", "users", "id"),
            ("results_overlay_sessions", "workspace_id", "workspaces", "id"),
            ("results_overlay_sessions", "station_id", "stations", "id"),
        }

        for expected in expected_fks:
            assert expected in fks, f"Expected foreign key {expected} not found in schema"
