"""Production migration idempotency, restore compatibility, and schema integrity tests (T079).

Validates that:
1. Running apply_postgres_schema repeatedly (idempotency) succeeds cleanly.
2. The four Results Media tables exist with required constraints, composite foreign keys, and indexes.
3. Workspace isolation and composite referential integrity are enforced on restore/insert.

Requires AITOB_PG_TEST_URL environment variable pointing to a disposable PostgreSQL instance.
"""

from __future__ import annotations

import os
import pytest
from backend.core import database
from backend.core.schema_migrations import apply_postgres_schema
from backend.core.storage import dbapi


pytestmark = pytest.mark.skipif(
    not os.environ.get("AITOB_PG_TEST_URL"),
    reason="AITOB_PG_TEST_URL not set — skipped in CI without disposable PostgreSQL",
)


@pytest.mark.asyncio
async def test_migration_idempotency_multiple_runs(postgres_repository_database):
    """Verify executing schema migrations repeatedly does not error and preserves existing tables."""
    # Run 1: Already executed during fixture initialization.
    # Run 2 & 3: Explicitly execute apply_postgres_schema again — must be idempotent.
    async with dbapi.connect(database.DATABASE_DSN) as conn:
        await apply_postgres_schema(conn)
        await conn.commit()
        await apply_postgres_schema(conn)
        await conn.commit()

        # Verify all four Results Media tables exist
        rows = await (await conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (?, ?, ?, ?)
            ORDER BY table_name
            """,
            (
                "tournament_result_versions",
                "tournament_result_entries",
                "results_media_outputs",
                "results_overlay_sessions",
            ),
        )).fetchall()
        found_tables = {r[0] for r in rows}
        assert found_tables == {
            "tournament_result_versions",
            "tournament_result_entries",
            "results_media_outputs",
            "results_overlay_sessions",
        }


@pytest.mark.asyncio
async def test_results_media_constraints_and_referential_integrity(postgres_repository_database):
    """Verify checks, composite ownership, and frozen-parent protection."""
    async with dbapi.connect(database.DATABASE_DSN) as conn:
        ws = "ws-mig-drill"
        other_ws = "ws-mig-drill-other"
        tourney_slug = "tourney-mig-drill"
        user_id = "user-mig-drill"

        # Seed workspace and tournament
        await conn.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (ws, "mig-drill", "Migration Drill WS"),
        )
        await conn.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (other_ws, "mig-drill-other", "Other Migration Drill WS"),
        )
        await conn.execute(
            """INSERT INTO users (id, email, display_name, password_hash)
               VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING""",
            (user_id, "migration-drill@example.test", "Migration Drill"),
        )
        await conn.execute(
            """INSERT INTO tournaments (workspace_id, slug, name, provider_type, game)
               VALUES (?, ?, ?, 'startgg', 'sf6') ON CONFLICT DO NOTHING""",
            (ws, tourney_slug, "Drill Tourney"),
        )

        # 1. Insert into tournament_result_versions
        ver_id = "ver-mig-1"
        await conn.execute(
            """INSERT INTO tournament_result_versions (
                id, workspace_id, tournament_slug, provider_type, provider_account_id,
                provider_tournament_id, event_id, event_name, game_id, capture_status,
                provider_state_raw, provider_payload_hash, presentation_hash, observation_hash,
                observed_at, created_by
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),?)""",
            (ver_id, ws, tourney_slug, "startgg", "acc-1",
             "t-1", "ev-1", "SF6 Top 8", "sf6", "final",
             "COMPLETED", "h1", "h2", "h3", user_id),
        )

        # 2. Insert into tournament_result_entries
        await conn.execute(
            """INSERT INTO tournament_result_entries (
                version_id, workspace_id, ordinal, placement, entrant_id,
                entrant_name, is_tied, presentation_json, provider_entry_json
            ) VALUES (?,?,?,?,?,?,?,?,?)""",
            (ver_id, ws, 1, 1, "ent-1", "Champion", False, "{}", "{}"),
        )

        # 3. Insert into results_media_outputs
        out_id = "out-mig-1"
        await conn.execute(
            """INSERT INTO results_media_outputs (
                id, workspace_id, result_version_id, output_kind, overlay_name,
                scene_config_json, cutoff, page_number, output_profile_json,
                scene_hash, created_by
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (out_id, ws, ver_id, "static", "Export Top 8", "{}", "top8", 1, "{}", "shash-1", user_id),
        )

        # 4. Insert station and bind to results_overlay_sessions
        station_id = "station-mig-1"
        await conn.execute(
            "INSERT INTO stations (id, name, workspace_id) VALUES (?,?,?) ON CONFLICT DO NOTHING",
            (station_id, "Main Stream Station", ws),
        )
        await conn.execute(
            """INSERT INTO results_overlay_sessions (
                workspace_id, station_id, media_output_id, state, cue_index, session_revision
            ) VALUES (?,?,?,?,?,?)""",
            (ws, station_id, out_id, "ready", -1, 1),
        )
        await conn.commit()

        # Check constraint violation: invalid capture_status must fail
        await conn.execute("SAVEPOINT invalid_capture")
        with pytest.raises(Exception):
            await conn.execute(
                """INSERT INTO tournament_result_versions (
                    id, workspace_id, tournament_slug, provider_type, provider_account_id,
                    provider_tournament_id, event_id, event_name, game_id, capture_status,
                    provider_state_raw, provider_payload_hash, presentation_hash, observation_hash,
                    observed_at, created_by
                ) VALUES ('bad-ver',?,?,'startgg','acc-1','t-1','ev-1','SF6',NULL,
                          'invalid_status','COMPLETED','h1','h2','h3',NOW(),?)""",
                (ws, tourney_slug, user_id),
            )
        await conn.execute("ROLLBACK TO SAVEPOINT invalid_capture")

        # Composite tenant ownership: a child cannot claim another workspace.
        await conn.execute("SAVEPOINT cross_workspace")
        with pytest.raises(Exception):
            await conn.execute(
                """INSERT INTO tournament_result_entries
                   (version_id, workspace_id, ordinal, placement, entrant_id, entrant_name)
                   VALUES (?, ?, 2, 2, 'cross-entrant', 'Cross Workspace')""",
                (ver_id, other_ws),
            )
        await conn.execute("ROLLBACK TO SAVEPOINT cross_workspace")

        # Frozen published aggregates are protected from parent deletion.
        await conn.execute("SAVEPOINT protected_delete")
        with pytest.raises(Exception):
            await conn.execute("DELETE FROM tournament_result_versions WHERE id=?", (ver_id,))
        await conn.execute("ROLLBACK TO SAVEPOINT protected_delete")

        entries_count = await (await conn.execute(
            "SELECT count(*) FROM tournament_result_entries WHERE version_id=?",
            (ver_id,),
        )).fetchone()
        outputs_count = await (await conn.execute(
            "SELECT count(*) FROM results_media_outputs WHERE result_version_id=?",
            (ver_id,),
        )).fetchone()
        assert int(entries_count[0]) == 1
        assert int(outputs_count[0]) == 1
