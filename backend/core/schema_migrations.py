"""Transactional, serialized PostgreSQL schema upgrades with durable receipts.

The existing additive schema definitions remain authoritative. Each converted
statement has a content-addressed receipt; no successful DDL is silently retried.
This does not repair or reinterpret user data.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid

from backend.core.database_schema import INDEXES, MIGRATIONS, TABLE_SCHEMAS
def migration_statements():
    for phase, statements in (("table", TABLE_SCHEMAS), ("addition", MIGRATIONS), ("index", INDEXES)):
        for statement in statements:
            normalized = statement.strip()
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            yield f"{phase}:{digest}", phase, normalized


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
    await apply_results_media_constraint_migrations(db)
    await consolidate_legacy_player_links(db)
    await promote_linked_overrides_to_archive(db)
    await promote_linked_provider_data_to_archive(db)
    await apply_tournament_setup_constraints(db)
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
    "tournament_setup_drafts", "integration_connection_health",
    "workspace_ai_configs", "provider_scope_bindings", "match_call_occurrences",
    "tournament_brands", "tournament_operating_profiles", "tournament_discord_bindings",
    "tournament_registration_configs", "tournament_player_enrollments",
    "player_identity_verification_challenges", "provider_roster_snapshots",
    "bot_experience_profiles", "tournament_setup_templates", "tournament_readiness_snapshots",
    "discord_oauth_states",
    "provider_oauth_states",
    "player_profiles",
    "player_provider_identities",
    "player_game_profiles",
    "player_character_defaults",
    "tournament_entrant_overrides",
    "tournament_result_versions",
    "tournament_result_entries",
    "results_media_outputs",
    "results_overlay_sessions",
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


async def _ensure_named_constraint(db, table: str, name: str, definition: str) -> None:
    exists = await (await db.execute(
        "SELECT 1 FROM pg_constraint WHERE conrelid=?::regclass AND conname=?",
        (table, name),
    )).fetchone()
    if not exists:
        await db.execute(f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" {definition}')


async def apply_results_media_constraint_migrations(db) -> None:
    """Enforce tenant ownership edges for frozen results aggregates.

    A globally unique child id is not sufficient proof that the caller's
    ``workspace_id`` owns its parent.  Composite keys make cross-Workspace
    references impossible even if an application predicate regresses.
    """
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_trv_workspace_id "
        "ON tournament_result_versions(workspace_id, id)"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_rmo_workspace_id "
        "ON results_media_outputs(workspace_id, id)"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_stations_workspace_id "
        "ON stations(workspace_id, id)"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_player_profiles_workspace_id "
        "ON player_profiles(workspace_id, id)"
    )

    await _ensure_named_constraint(
        db,
        "tournament_result_entries",
        "fk_tre_workspace_version",
        "FOREIGN KEY (workspace_id, version_id) "
        "REFERENCES tournament_result_versions(workspace_id, id) ON DELETE RESTRICT",
    )
    await _ensure_named_constraint(
        db,
        "tournament_result_entries",
        "fk_tre_workspace_profile",
        "FOREIGN KEY (workspace_id, player_profile_id) "
        "REFERENCES player_profiles(workspace_id, id) ON DELETE RESTRICT",
    )
    await _ensure_named_constraint(
        db,
        "results_media_outputs",
        "fk_rmo_workspace_version",
        "FOREIGN KEY (workspace_id, result_version_id) "
        "REFERENCES tournament_result_versions(workspace_id, id) ON DELETE RESTRICT",
    )
    await _ensure_named_constraint(
        db,
        "results_overlay_sessions",
        "fk_ros_workspace_station",
        "FOREIGN KEY (workspace_id, station_id) "
        "REFERENCES stations(workspace_id, id) ON DELETE CASCADE",
    )
    await _ensure_named_constraint(
        db,
        "results_overlay_sessions",
        "fk_ros_workspace_output",
        "FOREIGN KEY (workspace_id, media_output_id) "
        "REFERENCES results_media_outputs(workspace_id, id) ON DELETE RESTRICT",
    )

    await _ensure_named_constraint(
        db,
        "tournament_result_versions",
        "ck_trv_entry_count_nonnegative",
        "CHECK (entry_count >= 0)",
    )
    await _ensure_named_constraint(
        db,
        "tournament_result_entries",
        "ck_tre_ordinal_positive",
        "CHECK (ordinal > 0)",
    )
    await _ensure_named_constraint(
        db,
        "results_media_outputs",
        "ck_rmo_export_receipt_pair",
        "CHECK ((export_byte_size IS NULL) = (export_sha256 IS NULL))",
    )
    await _ensure_named_constraint(
        db,
        "results_overlay_sessions",
        "ck_ros_cue_index",
        "CHECK (cue_index >= -1)",
    )
    await _ensure_named_constraint(
        db,
        "results_overlay_sessions",
        "ck_ros_revision",
        "CHECK (session_revision >= 0)",
    )


async def consolidate_legacy_player_links(db) -> None:
    """Move historical entrant links onto Player Archive records.

    The old ``players`` table is read only to preserve organizer links created
    before Player Archive existed. Each link becomes a reference to one
    workspace-scoped archive profile, then the old Discord column is cleared.
    Provider, bracket, and active-match state are intentionally untouched.
    """
    async with db.execute(
        """SELECT DISTINCT ON (COALESCE(t.workspace_id, l.workspace_id), p.discord_id)
                  COALESCE(t.workspace_id, l.workspace_id) AS workspace_id,
                  p.discord_id, p.gamer_tag, p.team, p.country, p.avatar_path
             FROM tournament_player_links l
             INNER JOIN players p ON p.discord_id = l.player_discord_id
             INNER JOIN tournaments t ON t.slug = l.tournament_slug
            WHERE l.player_profile_id IS NULL
              AND p.discord_id IS NOT NULL
              AND COALESCE(t.workspace_id, l.workspace_id) IS NOT NULL
            ORDER BY COALESCE(t.workspace_id, l.workspace_id), p.discord_id, l.created_at ASC"""
    ) as cursor:
        rows = await cursor.fetchall()
    for raw_row in rows:
        row = dict(raw_row)
        workspace_id = row["workspace_id"]
        discord_id = row["discord_id"]
        gamer_tag = row["gamer_tag"]
        team = row["team"]
        country = row["country"]
        avatar_path = row["avatar_path"]
        await db.execute(
            """INSERT INTO player_profiles
                   (id, workspace_id, display_name, prefix, country, avatar_url, discord_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
               ON CONFLICT (workspace_id, discord_id) WHERE discord_id IS NOT NULL DO NOTHING""",
            (
                str(uuid.uuid4()), workspace_id,
                str(gamer_tag or discord_id), team, country, avatar_path, discord_id,
            ),
        )
    await db.execute(
        """UPDATE tournament_player_links l
               SET player_profile_id = pr.id,
                   player_discord_id = NULL
              FROM tournaments t, player_profiles pr
             WHERE l.player_profile_id IS NULL
               AND t.slug = l.tournament_slug
               AND pr.discord_id = l.player_discord_id
               AND pr.workspace_id = COALESCE(t.workspace_id, l.workspace_id)"""
    )


async def promote_linked_overrides_to_archive(db) -> None:
    """Fill missing archive facts from existing linked entrant projections.

    Earlier releases saved organizer-provided prefix, country, avatar, and
    character selection only on a tournament entrant override.  Those facts
    now belong to Player Archive. Existing non-empty archive fields always win
    so this backfill cannot overwrite a later organizer profile edit.
    """
    await db.execute(
        """UPDATE player_profiles profile
               SET display_name = COALESCE(NULLIF(profile.display_name, ''), NULLIF(override.display_name, '')),
                   prefix = COALESCE(NULLIF(profile.prefix, ''), NULLIF(override.prefix, '')),
                   country = COALESCE(NULLIF(profile.country, ''), NULLIF(override.country, '')),
                   avatar_url = COALESCE(NULLIF(profile.avatar_url, ''), NULLIF(override.avatar_url, '')),
                   updated_at = CASE
                       WHEN NULLIF(profile.prefix, '') IS NULL AND NULLIF(override.prefix, '') IS NOT NULL
                         OR NULLIF(profile.country, '') IS NULL AND NULLIF(override.country, '') IS NOT NULL
                         OR NULLIF(profile.avatar_url, '') IS NULL AND NULLIF(override.avatar_url, '') IS NOT NULL
                       THEN CURRENT_TIMESTAMP ELSE profile.updated_at END
              FROM tournament_entrant_overrides override
              JOIN tournament_player_links link
                ON link.workspace_id = override.workspace_id
               AND link.tournament_slug = override.tournament_slug
               AND link.entrant_id = override.entrant_id
             WHERE profile.id = link.player_profile_id
               AND profile.workspace_id = link.workspace_id"""
    )
    async with db.execute(
        """SELECT override.workspace_id, link.player_profile_id, tournament.game,
                  override.character_id, override.character_name, override.character_image_url,
                  profile.display_name
             FROM tournament_entrant_overrides override
             JOIN tournament_player_links link
               ON link.workspace_id = override.workspace_id
              AND link.tournament_slug = override.tournament_slug
              AND link.entrant_id = override.entrant_id
             JOIN tournaments tournament ON tournament.slug = override.tournament_slug
             JOIN player_profiles profile
               ON profile.id = link.player_profile_id AND profile.workspace_id = link.workspace_id
            WHERE NULLIF(override.character_id, '') IS NOT NULL
              AND NULLIF(tournament.game, '') IS NOT NULL"""
    ) as cursor:
        character_rows = await cursor.fetchall()
    for raw_row in character_rows:
        row = dict(raw_row)
        workspace_id = row["workspace_id"]
        profile_id = row["player_profile_id"]
        game_id = row["game"]
        character_id = row["character_id"]
        character_name = row["character_name"]
        character_image_url = row["character_image_url"]
        display_name = row["display_name"]
        game_profile = await (await db.execute(
            """INSERT INTO player_game_profiles
                   (id, workspace_id, player_profile_id, game_id, in_game_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
               ON CONFLICT (workspace_id, player_profile_id, game_id)
               DO UPDATE SET updated_at = player_game_profiles.updated_at
               RETURNING id""",
            (str(uuid.uuid4()), workspace_id, profile_id, game_id, display_name),
        )).fetchone()
        await db.execute(
            "UPDATE player_character_defaults SET is_primary = FALSE WHERE workspace_id=? AND player_game_profile_id=?",
            (workspace_id, game_profile[0]),
        )
        await db.execute(
            """INSERT INTO player_character_defaults
                   (id, workspace_id, player_game_profile_id, character_id, character_name, character_image_url, is_primary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, TRUE, CURRENT_TIMESTAMP)
               ON CONFLICT (workspace_id, player_game_profile_id, character_id)
               DO UPDATE SET character_name=excluded.character_name,
                             character_image_url=excluded.character_image_url,
                             is_primary=TRUE""",
            (str(uuid.uuid4()), workspace_id, game_profile[0], character_id, character_name, character_image_url),
        )


async def promote_linked_provider_data_to_archive(db) -> None:
    """Fill linked profile defaults from the entrant's actual provider event.

    A tournament may contain several games, so ``tournaments.game`` cannot be
    used for participant game data. The imported event containing the entrant
    is the authoritative scope for prefix, country, CFN, and character default.
    """
    async with db.execute(
        """SELECT link.workspace_id, link.tournament_slug, link.entrant_id,
                  link.player_profile_id, tournament.raw_data,
                  profile.display_name, profile.prefix, profile.country
             FROM tournament_player_links link
             JOIN tournaments tournament ON tournament.slug = link.tournament_slug
             JOIN player_profiles profile
               ON profile.id = link.player_profile_id AND profile.workspace_id = link.workspace_id
            WHERE link.player_profile_id IS NOT NULL"""
    ) as cursor:
        linked_rows = await cursor.fetchall()
    async with db.execute("SELECT id, workspace_id, character_id, character_name, character_image_url FROM player_overrides") as cursor:
        legacy_overrides = {
            (str(row["workspace_id"]), str(row["id"])): dict(row)
            for row in await cursor.fetchall()
            if row["workspace_id"]
        }

    for raw_row in linked_rows:
        row = dict(raw_row)
        try:
            raw_data = json.loads(row["raw_data"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        events = raw_data.get("events") or (raw_data.get("tournament") or {}).get("events") or []
        entrant = None
        event = None
        for candidate_event in events:
            nodes = (candidate_event.get("entrants") or {}).get("nodes") or []
            entrant = next((node for node in nodes if str(node.get("id")) == str(row["entrant_id"])), None)
            if entrant:
                event = candidate_event
                break
        if not entrant or not event:
            continue

        prefix = str(entrant.get("prefix") or "").strip() or None
        country = str(entrant.get("country") or "").strip() or None
        gamertag = str(entrant.get("gamertag") or entrant.get("name") or row["display_name"] or "").strip() or None
        cfn = str(entrant.get("cfn") or "").strip() or None
        videogame = event.get("videogame") if isinstance(event.get("videogame"), dict) else {}
        game_id = str(videogame.get("name") or "").strip()
        await db.execute(
            """UPDATE player_profiles
                   SET prefix=COALESCE(NULLIF(prefix, ''), ?),
                       country=COALESCE(NULLIF(country, ''), ?),
                       updated_at=CASE WHEN (NULLIF(prefix, '') IS NULL AND CAST(? AS TEXT) IS NOT NULL)
                                           OR (NULLIF(country, '') IS NULL AND CAST(? AS TEXT) IS NOT NULL)
                                       THEN CURRENT_TIMESTAMP ELSE updated_at END
                 WHERE id=? AND workspace_id=?""",
            (prefix, country, prefix, country, row["player_profile_id"], row["workspace_id"]),
        )
        if not game_id:
            continue
        game_profile = await (await db.execute(
            """INSERT INTO player_game_profiles
                   (id, workspace_id, player_profile_id, game_id, in_game_name, in_game_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
               ON CONFLICT (workspace_id, player_profile_id, game_id)
               DO UPDATE SET in_game_name=COALESCE(NULLIF(player_game_profiles.in_game_name, ''), excluded.in_game_name),
                             in_game_id=COALESCE(NULLIF(player_game_profiles.in_game_id, ''), excluded.in_game_id),
                             updated_at=player_game_profiles.updated_at
               RETURNING id""",
            (str(uuid.uuid4()), row["workspace_id"], row["player_profile_id"], game_id, gamertag, cfn),
        )).fetchone()
        legacy = legacy_overrides.get((str(row["workspace_id"]), str(row["entrant_id"])))
        if not legacy or not legacy.get("character_id"):
            continue
        await db.execute(
            "UPDATE player_character_defaults SET is_primary=FALSE WHERE workspace_id=? AND player_game_profile_id=?",
            (row["workspace_id"], game_profile[0]),
        )
        await db.execute(
            """INSERT INTO player_character_defaults
                   (id, workspace_id, player_game_profile_id, character_id, character_name, character_image_url, is_primary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, TRUE, CURRENT_TIMESTAMP)
               ON CONFLICT (workspace_id, player_game_profile_id, character_id)
               DO UPDATE SET character_name=excluded.character_name,
                             character_image_url=excluded.character_image_url,
                             is_primary=TRUE""",
            (
                str(uuid.uuid4()), row["workspace_id"], game_profile[0],
                legacy["character_id"], legacy.get("character_name") or legacy["character_id"], legacy.get("character_image_url"),
            ),
        )


async def _ensure_foreign_key(
    db, source_table: str, source_column: str, target_table: str, target_column: str
) -> None:
    row = await (await db.execute(
        """SELECT 1
             FROM pg_constraint c
             JOIN pg_class r ON r.oid=c.conrelid
             JOIN pg_attribute a ON a.attrelid=r.oid AND a.attnum=ANY(c.conkey)
            WHERE c.contype='f' AND r.relname=? AND a.attname=?
              AND c.confrelid=?::regclass""",
        (source_table, source_column, target_table),
    )).fetchone()
    if row:
        return
    suffix = hashlib.sha256(
        f"{source_table}:{source_column}:{target_table}:{target_column}".encode()
    ).hexdigest()[:10]
    await db.execute(
        f'ALTER TABLE "{source_table}" ADD CONSTRAINT "fk_phase11_{suffix}" '
        f'FOREIGN KEY ("{source_column}") REFERENCES "{target_table}"("{target_column}")'
    )


async def _normalize_discord_destination_references(db) -> None:
    """Upgrade wizard-era channel IDs to integration destination IDs.

    Early Feature 004 builds stored Discord external channel IDs directly in
    the two binding columns even though the final schema defines those columns
    as foreign keys. Preserve those channels by reusing an existing destination
    or creating a deterministic migration destination before adding the FKs.
    """
    for column, destination_type in (
        ("match_destination_id", "match_call_channel"),
        ("escalation_destination_id", "escalation_channel"),
    ):
        await db.execute(
            f"""INSERT INTO integration_destinations
                   (id, account_id, workspace_id, destination_type, external_id, display_name)
                SELECT 'phase11-' || md5(
                           b.discord_account_id || ':' || b.workspace_id || ':' || b."{column}"
                       ),
                       b.discord_account_id, b.workspace_id, ?, b."{column}",
                       'Migrated tournament destination'
                  FROM tournament_discord_bindings b
                 WHERE b."{column}" <> ''
                   AND NOT EXISTS (
                       SELECT 1 FROM integration_destinations by_id
                        WHERE by_id.id=b."{column}"
                   )
                   AND NOT EXISTS (
                       SELECT 1 FROM integration_destinations by_external
                        WHERE by_external.account_id=b.discord_account_id
                          AND by_external.workspace_id=b.workspace_id
                          AND by_external.external_id=b."{column}"
                   )
                ON CONFLICT DO NOTHING""",
            (destination_type,),
        )
        await db.execute(
            f"""UPDATE tournament_discord_bindings b
                   SET "{column}"=(
                       SELECT d.id
                         FROM integration_destinations d
                        WHERE d.account_id=b.discord_account_id
                          AND d.workspace_id=b.workspace_id
                          AND d.external_id=b."{column}"
                        ORDER BY d.created_at, d.id
                        LIMIT 1
                   )
                 WHERE NOT EXISTS (
                       SELECT 1 FROM integration_destinations by_id
                        WHERE by_id.id=b."{column}"
                   )
                   AND EXISTS (
                       SELECT 1 FROM integration_destinations by_external
                        WHERE by_external.account_id=b.discord_account_id
                          AND by_external.workspace_id=b.workspace_id
                          AND by_external.external_id=b."{column}"
                   )"""
        )


async def apply_tournament_setup_constraints(db):
    """Finish Feature 004 ownership and cross-aggregate PostgreSQL contracts."""
    await db.execute(
        "ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS id TEXT "
        "GENERATED ALWAYS AS (slug) STORED"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tournaments_canonical_id ON tournaments(id)"
    )
    await db.execute(
        """CREATE TABLE IF NOT EXISTS player_identities (
               id TEXT PRIMARY KEY,
               workspace_id TEXT NOT NULL REFERENCES workspaces(id),
               discord_user_id TEXT NOT NULL,
               prefix TEXT,
               gamertag TEXT,
               created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
               updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
               UNIQUE(workspace_id, discord_user_id)
           )"""
    )

    await db.execute(
        "ALTER TABLE ai_usage_ledger ADD COLUMN IF NOT EXISTS tournament_id TEXT"
    )
    await db.execute(
        "ALTER TABLE ai_usage_ledger ADD COLUMN IF NOT EXISTS integration_account_id TEXT"
    )
    await db.execute(
        "ALTER TABLE tournament_player_enrollments "
        "ALTER COLUMN provider_identity_link_id TYPE BIGINT "
        "USING NULLIF(provider_identity_link_id::TEXT, '')::BIGINT"
    )
    await db.execute(
        """UPDATE integration_accounts a
              SET workspace_id=a.owner_id
            WHERE a.workspace_id IS NULL
              AND EXISTS (SELECT 1 FROM workspaces w WHERE w.id=a.owner_id)"""
    )
    await db.execute(
        """UPDATE ai_usage_ledger u
              SET workspace_id=t.workspace_id,
                  tournament_id=t.id
             FROM tournaments t
            WHERE u.tournament_slug=t.slug
              AND (u.workspace_id IS NULL OR u.tournament_id IS NULL)"""
    )
    await db.execute(
        """UPDATE ai_usage_ledger u
              SET integration_account_id=c.selected_account_id
             FROM workspace_ai_configs c
            WHERE u.workspace_id=c.workspace_id
              AND u.integration_account_id IS NULL"""
    )
    await db.execute("ALTER TABLE integration_accounts ALTER COLUMN workspace_id SET NOT NULL")
    await db.execute("ALTER TABLE ai_usage_ledger ALTER COLUMN workspace_id SET NOT NULL")

    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_integration_accounts_workspace_identity "
        "ON integration_accounts(workspace_id, provider_type, external_account_id)"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_enrollments_workspace_discord "
        "ON tournament_player_enrollments(workspace_id, tournament_id, discord_user_id) "
        "WHERE discord_user_id IS NOT NULL"
    )
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_enrollments_workspace_entrant "
        "ON tournament_player_enrollments(workspace_id, tournament_id, provider_entrant_id) "
        "WHERE provider_entrant_id IS NOT NULL"
    )

    await _normalize_discord_destination_references(db)

    foreign_keys = (
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
    for edge in foreign_keys:
        await _ensure_foreign_key(db, *edge)
