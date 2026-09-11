from backend.core.storage import dbapi as aiosqlite, is_postgres, postgres_ddl
import datetime
import os
import json
import re
import uuid
from pathlib import Path
from typing import Optional
from backend.core.contracts.tournament_types import ProviderSet, ProviderSetState, ProviderEntrant

if os.getenv("AITOB_TESTING") == "1" and not os.getenv("DB_PATH"):
    raise RuntimeError("Tests require an explicit DB_PATH; refusing the operating database fallback.")
DB_PATH = os.getenv("DB_PATH", "backend/core/database.sqlite")

_BOOLEAN_COLUMNS = {
    "auto_dq_enabled", "is_verified", "hidden", "swapped", "bot_enabled",
    "resolved", "is_stream_match", "p1_ready", "p2_ready",
    "auto_dispatch_enabled", "auto_dispatch_on_stream", "ignore_activity_guard",
    "economy_sync_on_stale_open", "auto_dq_disarmed", "is_stream_station",
}


def _database_value(column: str, value):
    """Normalize legacy 0/1 callers at the repository boundary for PostgreSQL."""
    if column in _BOOLEAN_COLUMNS and value is not None:
        return bool(value)
    return value


class TournamentRemovalBlocked(ValueError):
    """A tournament still owns local operations that must be resolved first."""


_AUDIT_SECRET_KEYS = frozenset({
    "token", "access_token", "refresh_token", "password", "secret",
    "api_key", "bot_token", "authorization", "cookie", "content",
})


def _is_audit_secret_key(key: object) -> bool:
    """Recognize common credential aliases without treating ordinary IDs as secrets.

    Integrations use inconsistent casing and separators (``clientSecret``,
    ``X-Api-Key``, ``webhook_signing_key``).  Audit redaction is deliberately
    more conservative than API response projection: a value with a
    credential-shaped key is not useful operational evidence and must never
    be retained.  We avoid a blanket ``*key`` rule so safe identifiers such as
    ``match_key`` and ``provider_account_id`` remain traceable.
    """
    raw = str(key).strip().lower()
    normalized = "".join(char for char in raw if char.isalnum())
    if raw in _AUDIT_SECRET_KEYS or normalized in {
        "accesstoken", "refreshtoken", "password", "secret", "apikey",
        "bottoken", "authorization", "cookie", "content", "headers",
        "header", "clientsecret", "webhooksigningkey", "privatekey",
        "encryptionkey", "secretkey", "credentials", "credential",
    }:
        return True
    return normalized.endswith((
        "token", "password", "secret", "apikey", "authorization",
        "cookie", "credential", "credentials", "signingkey", "privatekey",
    ))


def _redact_audit_string(value: str) -> str:
    """Remove common credential fragments embedded in exception text.

    Keys are the primary audit boundary, but HTTP clients and database drivers
    sometimes include an Authorization header or a query-style credential in
    a single error string.  Keep the diagnostic text while removing the
    credential portion before it becomes durable audit data.
    """
    value = re.sub(
        r"(?i)\bbearer\s+[^\s,;]+",
        "Bearer [REDACTED]",
        value,
    )
    value = re.sub(
        r"(?i)\b(token|password|secret|api[_-]?key)\s*=\s*[^&\s,;]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        value,
    )
    return value[:1000]


def _redact_audit(value):
    if isinstance(value, dict):
        return {
            str(key): ("[REDACTED]" if _is_audit_secret_key(key) else _redact_audit(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_audit(item) for item in value]
    if isinstance(value, str):
        return _redact_audit_string(value)
    return value


async def record_audit_event(
    *, workspace_id: str, action: str, outcome: str,
    actor_id: str | None = None, target_type: str | None = None,
    target_id: str | None = None, trace_id: str | None = None,
    detail: dict | None = None,
) -> str:
    """Persist a structured, redacted audit event without secrets/content."""
    event_id = str(uuid.uuid4())
    safe_detail = json.dumps(_redact_audit(detail or {}), separators=(",", ":"))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO audit_events
               (id, workspace_id, actor_id, action, target_type, target_id,
                outcome, trace_id, detail_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, workspace_id, actor_id, action, target_type, target_id,
             outcome, trace_id, safe_detail),
        )
        await db.commit()
    return event_id


async def record_error_event(
    *,
    method: str,
    path: str,
    exception_type: str,
    workspace_id: str | None = None,
    trace_id: str | None = None,
    detail: dict | None = None,
) -> str | None:
    """Persist minimal, redacted server error telemetry.

    Error reporting must never turn an exception path into a second failure or
    a secret sink.  Only a bounded exception class, request method/path, trace
    id and recursively redacted operator metadata are retained.  Callers may
    safely use this from an exception handler; a database outage is swallowed
    and leaves the original HTTP failure unchanged.
    """
    event_id = str(uuid.uuid4())
    safe_detail = json.dumps(_redact_audit(detail or {}), separators=(",", ":"))
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO error_events
                   (id, workspace_id, trace_id, method, path, exception_type, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    workspace_id,
                    trace_id,
                    str(method or "UNKNOWN")[:16],
                    str(path or "")[:512],
                    str(exception_type or "Exception")[:160],
                    safe_detail[:4000],
                ),
            )
            await db.commit()
        return event_id
    except Exception:
        return None


async def init_db():
    if os.getenv("AITOB_TESTING") == "1":
        project_root = Path(__file__).resolve().parents[2]
        if Path(DB_PATH).resolve().is_relative_to(project_root):
            raise RuntimeError("Tests may not initialize a database inside the project workspace.")
    from backend.core.database_schema import TABLE_SCHEMAS, INDEXES, MIGRATIONS
    if is_postgres():
        from backend.core.schema_migrations import apply_postgres_schema
        async with aiosqlite.connect(DB_PATH) as db:
            await apply_postgres_schema(db)
            # Stations are Hub-local resources. A fresh PostgreSQL deployment
            # must receive the same deterministic seed as a fresh SQLite
            # development database before any reservation can be accepted.
            async with db.execute("SELECT COUNT(*) FROM stations") as cursor:
                station_count = int((await cursor.fetchone())[0])
            if station_count == 0:
                await db.execute("INSERT INTO stations (id, name) VALUES ('station_1', 'Station 1')")
                await db.execute("INSERT INTO stations (id, name) VALUES ('station_2', 'Station 2')")
            await db.execute("UPDATE stations SET public_id=id WHERE public_id IS NULL")
            await db.commit()
        from backend.core.workspace_auth import bootstrap_initial_owner_from_env
        await bootstrap_initial_owner_from_env()
        return
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        for schema in TABLE_SCHEMAS:
            await db.execute(schema)
        for m in MIGRATIONS:
            try:
                await db.execute(m)
                await db.commit()
            except Exception:
                pass
        # A migration can introduce a column used by a new index. Applying
        # indexes afterwards keeps upgrades from an older SQLite file safe.
        for idx in INDEXES:
            await db.execute(idx)

        # One-shot cleanup: purge any "preview_*" rows that earlier builds
        # inserted into active_matches before we filtered them out at sync
        # time. Preview sets are unresolved bracket placeholders that can't
        # be mutated on start.gg, so they have no business in the actionable
        # list. Idempotent — no-ops on a clean DB.
        await db.execute("DELETE FROM active_matches WHERE set_id LIKE 'preview%'")
        await db.commit()

        # Seed default stations if empty
        async with db.execute("SELECT COUNT(*) FROM stations") as c:
            count = (await c.fetchone())[0]
        if count == 0:
            await db.execute("INSERT INTO stations (id, name) VALUES ('station_1', 'Station 1')")
            await db.execute("INSERT INTO stations (id, name) VALUES ('station_2', 'Station 2')")
        await db.execute("UPDATE stations SET public_id=id WHERE public_id IS NULL")
        await db.commit()
    # Explicit one-time owner bootstrap. No account is created unless a deployer
    # provides both bootstrap variables; reruns never create another owner.
    from backend.core.workspace_auth import bootstrap_initial_owner_from_env
    await bootstrap_initial_owner_from_env()
# ── Players ────────────────────────────────────────────────────────────────
async def create_or_update_player(discord_id: str, workspace_id: str | None = None, **kwargs):
    if not kwargs:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        valid_cols = []
        async with db.execute("PRAGMA table_info(players)") as cursor:
            info = await cursor.fetchall()
            valid_cols = [row[1] for row in info]

        filtered_kwargs = {k: _database_value(k, v) for k, v in kwargs.items() if k in valid_cols}
        if not filtered_kwargs:
            return

        select_sql = "SELECT discord_id, workspace_id FROM players WHERE discord_id = ?"
        async with db.execute(select_sql, (discord_id,)) as cursor:
            exists = await cursor.fetchone()
        if exists and workspace_id is not None and len(exists) > 1 and exists[1] not in (None, workspace_id):
            raise PermissionError("Player belongs to another workspace")
        if not exists:
            columns = ['discord_id'] + list(filtered_kwargs.keys())
            if workspace_id is not None and 'workspace_id' in valid_cols:
                columns.append('workspace_id')
            placeholders = ['?'] * len(columns)
            values = [discord_id] + list(filtered_kwargs.values())
            if workspace_id is not None and 'workspace_id' in valid_cols:
                values.append(workspace_id)
            query = f"INSERT INTO players ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            await db.execute(query, values)
        else:
            set_clause = ', '.join([f"{k} = ?" for k in filtered_kwargs.keys()])
            values = list(filtered_kwargs.values()) + [discord_id]
            query = f"UPDATE players SET {set_clause} WHERE discord_id = ?"
            if workspace_id is not None and 'workspace_id' in valid_cols:
                query += " AND (workspace_id IS NULL OR workspace_id = ?)"
                values.append(workspace_id)
            await db.execute(query, values)
        await db.commit()

async def get_player(discord_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM players WHERE discord_id = ?"
        params: list = [discord_id]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_discord_id_by_startgg(startgg_id: str, workspace_id: str | None = None) -> str | None:
    """Resolve an explicitly linked Start.gg identity within one workspace.

    This repository boundary replaces the bot's former direct SQLite query. A
    missing workspace is intentionally treated as an unscoped legacy lookup
    for compatibility with pre-workspace callers; all runtime callers should
    pass the durable match workspace.
    """
    if not startgg_id:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        params: list = [str(startgg_id)]
        query = (
            "SELECT discord_id FROM players "
            "WHERE startgg_id = ? AND startgg_id IS NOT NULL AND startgg_id != ''"
        )
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        query += " ORDER BY discord_id LIMIT 1"
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return str(row[0]) if row else None

async def get_players_for_workspace(workspace_id: str | None = None) -> list[dict]:
    """Return the minimal player projection used by administrative tooling."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT discord_id, startgg_id, gamer_tag, cfn_id FROM players"
        params: list = []
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params.append(workspace_id)
        query += " ORDER BY discord_id"
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def list_players_for_workspace(workspace_id: str | None = None) -> list[dict]:
    """Return the complete player projection for the workspace API."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM players"
        params: list = []
        if workspace_id is not None:
            # A tenant projection must never include legacy/unowned rows. Those
            # rows remain visible only to explicit migration/owner tooling until
            # the controlled backfill assigns them an owner.
            query += " WHERE workspace_id = ?"
            params.append(workspace_id)
        query += " ORDER BY discord_id"
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def is_active_platform_admin(user_id: str) -> bool:
    """Return the platform-admin bit through the storage boundary.

    API dependencies must not open a database connection themselves: keeping
    this lookup here means PostgreSQL and explicitly-scoped test storage use
    the same repository transport and redaction rules.
    """
    if not user_id:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT is_platform_admin FROM users WHERE id = ? AND status = 'active'",
            (str(user_id),),
        ) as cursor:
            row = await cursor.fetchone()
    return bool(row and row[0])


async def get_tournament_player_links(tournament_slug: str, workspace_id: str | None = None) -> dict[str, dict]:
    """Return the explicitly confirmed player links for one imported bracket."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT l.entrant_id, l.player_discord_id, p.gamer_tag, p.avatar_path,
                   p.team, p.country, p.cfn_id
            FROM tournament_player_links l
            LEFT JOIN players p ON p.discord_id = l.player_discord_id
                                  AND (CAST(? AS TEXT) IS NULL OR p.workspace_id = l.workspace_id)
            WHERE l.tournament_slug = ?
              AND (CAST(? AS TEXT) IS NULL OR EXISTS (
                    SELECT 1 FROM tournaments t
                    WHERE t.slug = l.tournament_slug
                      AND t.workspace_id = ?
              ))
              AND (CAST(? AS TEXT) IS NULL OR l.workspace_id = ?)
            """,
            (workspace_id, tournament_slug, workspace_id, workspace_id, workspace_id, workspace_id),
        ) as cursor:
            rows = await cursor.fetchall()
    return {
        str(row["entrant_id"]): {
            "discord_id": str(row["player_discord_id"]),
            "gamer_tag": row["gamer_tag"] or str(row["player_discord_id"]),
            "avatar_path": row["avatar_path"],
            "team": row["team"],
            "country": row["country"],
            "cfn_id": row["cfn_id"],
        }
        for row in rows
    }


async def link_tournament_entrant(tournament_slug: str, entrant_id: str, discord_id: str, workspace_id: str | None = None) -> dict:
    """Persist a TO-confirmed entrant → aiTOB player link and apply it to live matches."""
    player = await get_player(discord_id, workspace_id)
    if not player:
        raise ValueError("Selected aiTOB player does not exist")

    async with aiosqlite.connect(DB_PATH) as db:
        if workspace_id is not None:
            tournament = await (await db.execute(
                "SELECT workspace_id FROM tournaments WHERE slug = ?", (tournament_slug,)
            )).fetchone()
            if not tournament or tournament[0] not in (None, workspace_id):
                raise PermissionError("Tournament belongs to another workspace")
        await db.execute(
            """
            INSERT INTO tournament_player_links (tournament_slug, entrant_id, player_discord_id, workspace_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(workspace_id, tournament_slug, entrant_id)
            DO UPDATE SET player_discord_id = excluded.player_discord_id,
                          created_at = CURRENT_TIMESTAMP
            """,
            (tournament_slug, str(entrant_id), str(discord_id), workspace_id),
        )
        # Apply immediately, so the bot and OBS do not need to wait for the next
        # provider polling cycle. The next sync also preserves this link.
        for slot in ("p1", "p2"):
            fields = [f"{slot}_discord = ?", f"{slot}_cfn = ?", f"{slot}_team = ?", f"{slot}_country = ?"]
            values = [str(discord_id), player.get("cfn_id"), player.get("team"), player.get("country")]
            if player.get("avatar_path"):
                fields.append(f"{slot}_avatar = ?")
                values.append(player["avatar_path"])
            values.extend([tournament_slug, str(entrant_id)])
            await db.execute(
                f"UPDATE active_matches SET {', '.join(fields)} "
                f"WHERE tournament_slug = ? AND {slot}_entrant_id = ?"
                + (" AND (workspace_id = ? OR workspace_id IS NULL)" if workspace_id is not None else ""),
                values + ([workspace_id] if workspace_id is not None else []),
            )
        await db.commit()
    return {
        "discord_id": str(discord_id),
        "gamer_tag": player.get("gamer_tag") or str(discord_id),
        "avatar_path": player.get("avatar_path"),
        "team": player.get("team"),
        "country": player.get("country"),
        "cfn_id": player.get("cfn_id"),
    }


async def unlink_tournament_entrant(tournament_slug: str, entrant_id: str, workspace_id: str | None = None) -> bool:
    """Remove a TO-confirmed link and disconnect that entrant from Hub-only profile data."""
    async with aiosqlite.connect(DB_PATH) as db:
        if workspace_id is not None:
            tournament = await (await db.execute(
                "SELECT workspace_id FROM tournaments WHERE slug = ?", (tournament_slug,)
            )).fetchone()
            if not tournament or tournament[0] not in (None, workspace_id):
                return False
        async with db.execute(
            "SELECT player_discord_id FROM tournament_player_links WHERE tournament_slug = ? AND entrant_id = ? AND (CAST(? AS TEXT) IS NULL OR workspace_id = ?)",
            (tournament_slug, str(entrant_id), workspace_id, workspace_id),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False
        discord_id = str(row[0])
        await db.execute(
            "DELETE FROM tournament_player_links WHERE tournament_slug = ? AND entrant_id = ? AND (CAST(? AS TEXT) IS NULL OR workspace_id = ?)",
            (tournament_slug, str(entrant_id), workspace_id, workspace_id),
        )
        # A later Start.gg sync may restore a native Start.gg account link.
        for slot in ("p1", "p2"):
            await db.execute(
                f"UPDATE active_matches SET {slot}_discord = NULL, {slot}_cfn = NULL "
                f"WHERE tournament_slug = ? AND {slot}_entrant_id = ? AND {slot}_discord = ?"
                + (" AND (workspace_id = ? OR workspace_id IS NULL)" if workspace_id is not None else ""),
                (tournament_slug, str(entrant_id), discord_id) + ((workspace_id,) if workspace_id is not None else ()),
            )
        await db.commit()
    return True

async def get_all_tournament_slugs(workspace_id: str | None = None) -> list[str]:
    """Return tracked tournament slugs, optionally limited to one workspace."""
    async with aiosqlite.connect(DB_PATH) as db:
        query, params = "SELECT slug FROM tournaments", []
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def sync_player_cfns_to_matches(discord_id: str, workspace_id: str | None = None):
    """Copy a player's cfn_id from the players table into any active matches they appear in.

    Called after cfn_id is written (either at verify-confirm from start.gg or via the
    cfn_pending DM step) so the stream overlay always has an up-to-date CFN without
    requiring a full bracket re-sync.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        scope = " AND workspace_id = ?" if workspace_id is not None else ""
        scope_params = (workspace_id,) if workspace_id is not None else ()
        await db.execute(
            "UPDATE active_matches SET p1_cfn = (SELECT cfn_id FROM players WHERE discord_id = ?) "
            "WHERE p1_discord = ?" + scope,
            (discord_id, discord_id) + scope_params,
        )
        await db.execute(
            "UPDATE active_matches SET p2_cfn = (SELECT cfn_id FROM players WHERE discord_id = ?) "
            "WHERE p2_discord = ?" + scope,
            (discord_id, discord_id) + scope_params,
        )
        await db.commit()


async def get_verified_players_missing_avatar(workspace_id: str | None = None) -> list[dict]:
    """Verified players who still have no broadcast avatar on file.

    Backs the Hub AI 'remind players to upload avatars' tool. Returns the
    fields needed to DM each player in their own language.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = ("SELECT discord_id, startgg_id, gamer_tag, preferred_language "
                 "FROM players WHERE is_verified = TRUE "
                 "AND (avatar_path IS NULL OR avatar_path = '')")
        params: list = []
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_verified_players_missing_profile(workspace_id: str | None = None) -> list[dict]:
    """Verified players missing an avatar, a CFN ID, or both.

    Backs audit_registration_tool. Returns enough fields for the agent to send
    targeted DM reminders for whichever piece(s) of the profile are absent.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = (
            "SELECT discord_id, gamer_tag, preferred_language, avatar_path, cfn_id "
            "FROM players WHERE is_verified = TRUE "
            "  AND ((avatar_path IS NULL OR avatar_path = '') "
            "       OR (cfn_id IS NULL OR cfn_id = ''))"
        )
        params: list = []
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

# ── Overlays ───────────────────────────────────────────────────────────────
async def save_overlay(name: str, config: str, workspace_id: str | None = None):
    if not isinstance(config, str):
        try:
            config = json.dumps(config)
        except Exception as e:
            print(f"Error serializing overlay config: {e}")
    async with aiosqlite.connect(DB_PATH) as db:
        # The legacy table has a global UNIQUE(name) constraint.  Do not let
        # that compatibility constraint turn an update from one workspace into
        # a cross-tenant overwrite; a later ownership migration may relax the
        # uniqueness to (workspace_id, name).
        async with db.execute("SELECT workspace_id FROM overlays WHERE name = ?", (name,)) as cursor:
            existing = await cursor.fetchone()
        if existing and workspace_id is not None and existing[0] not in (None, workspace_id):
            raise PermissionError("Overlay belongs to another workspace")
        await db.execute('''
            INSERT INTO overlays (name, config, workspace_id) VALUES (?, ?, ?)
            ON CONFLICT(workspace_id, name) DO UPDATE SET config = excluded.config
        ''', (name, config, workspace_id))
        await db.commit()

async def get_overlays(workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query, params = "SELECT * FROM overlays", ()
        if workspace_id is not None:
            query, params = query + " WHERE workspace_id=?", (workspace_id,)
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def delete_overlay(name: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query, params = "DELETE FROM overlays WHERE name = ?", [name]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        await db.execute(query, params)
        await db.commit()

# ── Tournaments ────────────────────────────────────────────────────────────
async def upsert_tournament(slug: str, name: str, event_name: str, event_id: str, game: str, raw_data: str,
                            provider_type: str = "startgg", provider_tournament_id: str | None = None,
                            provider_subdomain: str | None = None,
                            provider_account_id: str | None = None,
                            workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, provider_type, provider_tournament_id, provider_subdomain, provider_account_id, workspace_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name, event_name=excluded.event_name,
                event_id=excluded.event_id, game=excluded.game, raw_data=excluded.raw_data,
                provider_type=excluded.provider_type,
                provider_tournament_id=COALESCE(excluded.provider_tournament_id, tournaments.provider_tournament_id),
                provider_subdomain=COALESCE(excluded.provider_subdomain, tournaments.provider_subdomain),
                provider_account_id=COALESCE(tournaments.provider_account_id, excluded.provider_account_id)
        ''', (slug, name, event_name, event_id, game, raw_data, provider_type, provider_tournament_id, provider_subdomain, provider_account_id, workspace_id))
        await db.commit()

async def update_tournament_settings(slug: str, workspace_id: str | None = None, **kwargs):
    if not kwargs:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        valid_cols = []
        async with db.execute("PRAGMA table_info(tournaments)") as cursor:
            info = await cursor.fetchall()
            valid_cols = [row[1] for row in info]

        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_cols}
        if not filtered_kwargs:
            return

        set_clause = ', '.join([f"{k} = ?" for k in filtered_kwargs.keys()])
        values = list(filtered_kwargs.values()) + [slug]
        where = "slug = ?"
        if workspace_id is not None and "workspace_id" in valid_cols:
            where += " AND workspace_id = ?"
            values.append(workspace_id)
        await db.execute(f"UPDATE tournaments SET {set_clause} WHERE {where}", values)
        if "bot_manage_limit" in kwargs:
            limit_setting = kwargs["bot_manage_limit"]
            db.row_factory = aiosqlite.Row
            match_query = "SELECT set_id, round_name, phase_group FROM active_matches WHERE tournament_slug = ?"
            match_params: list = [slug]
            if workspace_id is not None:
                match_query += " AND workspace_id = ?"
                match_params.append(workspace_id)
            async with db.execute(match_query, match_params) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
            update_data = []
            for r in rows:
                bot_enabled = should_bot_manage_match(r["round_name"], r["phase_group"], limit_setting)
                update_data.append((bot_enabled, r["set_id"]))
            if update_data:
                await db.executemany("UPDATE active_matches SET bot_enabled = ? WHERE set_id = ?", update_data)
        await db.commit()

async def get_tournaments(workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM tournaments"
        params: tuple = ()
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params = (workspace_id,)
        query += " ORDER BY created_at DESC"
        async with db.execute(query, params) as cursor:
            rows = [dict(r) for r in await cursor.fetchall()]
    for row in rows:
        row["provider_type"] = row.get("provider_type") or "startgg"
        row["provider_tournament_id"] = row.get("provider_tournament_id") or row.get("slug")
    return rows

async def get_tournament(slug: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM tournaments WHERE slug = ?"
        params: tuple = (slug,)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params += (workspace_id,)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            result = dict(row) if row else None
    if result:
        result["provider_type"] = result.get("provider_type") or "startgg"
        result["provider_tournament_id"] = result.get("provider_tournament_id") or result.get("slug")
    return result


async def get_tournament_workspace_id(slug: str) -> str | None:
    """Resolve a tournament's durable owner for bot-side scoped operations."""
    if not slug:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT workspace_id FROM tournaments WHERE slug = ?", (slug,)) as cursor:
            row = await cursor.fetchone()
    return str(row[0]) if row and row[0] else None


async def get_fresh_provider_locator_alias(
    provider_type: str,
    provider_account_id: str,
    community_id: str | None,
    locator_key: str,
) -> dict | None:
    """Return a recently resolved identity without contacting the provider."""
    freshness_clause = "CURRENT_TIMESTAMP - INTERVAL '1 day'" if is_postgres() else "datetime('now', '-1 day')"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""
            SELECT a.*, t.name, t.raw_data, t.provider_tournament_id, t.provider_subdomain
            FROM provider_locator_aliases a
            JOIN tournaments t ON t.slug = a.tournament_slug
            WHERE a.provider_type = ? AND a.provider_account_id = ?
              AND a.community_id = ? AND a.locator_key = ?
              AND a.resolved_at >= {freshness_clause}
            """,
            (provider_type, provider_account_id, community_id or "", locator_key),
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def record_media_asset(
    *, workspace_id: str, asset_type: str, storage_url: str,
    owner_type: str | None = None, owner_id: str | None = None,
    storage_key: str | None = None, mime_type: str | None = None,
    byte_size: int | None = None, width: int | None = None,
    height: int | None = None,
) -> dict:
    """Record a newly uploaded asset without exposing filesystem details."""
    asset_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO media_assets
               (id, workspace_id, asset_type, owner_type, owner_id,
                storage_url, storage_key, mime_type, byte_size, width, height)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, workspace_id, asset_type, owner_type, owner_id,
             storage_url, storage_key, mime_type, byte_size, width, height),
        )
        await db.commit()
    return {"id": asset_id, "workspace_id": workspace_id, "asset_type": asset_type, "storage_url": storage_url}


async def list_media_assets(workspace_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT id, workspace_id, asset_type, owner_type, owner_id,
                      storage_url, storage_key, mime_type, byte_size, width, height,
                      created_at
                 FROM media_assets
                WHERE workspace_id = ? AND deleted_at IS NULL
                ORDER BY created_at DESC""",
            (workspace_id,),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


def _overlay_config_references_asset(config: object, references: set[str]) -> bool:
    """Return whether a flexible overlay JSON document still points at an asset.

    Overlay presets deliberately accept arbitrary nested element properties, so
    reference checks cannot rely on one particular key such as ``src`` or
    ``background_url``.  Be conservative for deletion: a filename-qualified
    URL is enough to keep the managed object alive until the organizer removes
    the reference from the preset.
    """
    if isinstance(config, dict):
        return any(_overlay_config_references_asset(value, references) for value in config.values())
    if isinstance(config, (list, tuple)):
        return any(_overlay_config_references_asset(value, references) for value in config)
    if not isinstance(config, str):
        return False
    value = config.strip()
    return any(value == reference or value.rstrip("/").endswith("/" + reference)
               for reference in references if reference)


async def delete_media_asset(asset_id: str, workspace_id: str) -> bool:
    """Soft-delete an asset only when it is owned and no live row references it."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT storage_url, storage_key FROM media_assets WHERE id=? AND workspace_id=? AND deleted_at IS NULL",
            (asset_id, workspace_id),
        ) as cursor:
            asset = await cursor.fetchone()
        if not asset:
            return False
        url, key = asset[0], asset[1]
        checks = (
            ("SELECT 1 FROM players WHERE workspace_id=? AND avatar_path IN (?, ?) LIMIT 1", (workspace_id, url, key or "")),
            ("SELECT 1 FROM player_overrides WHERE avatar_url IN (?, ?) LIMIT 1", (url, key or "")),
            ("SELECT 1 FROM active_matches WHERE workspace_id=? AND (p1_avatar IN (?, ?) OR p2_avatar IN (?, ?)) LIMIT 1", (workspace_id, url, key or "", url, key or "")),
        )
        for query, params in checks:
            async with db.execute(query, params) as cursor:
                if await cursor.fetchone():
                    raise ValueError("Asset is still referenced by an active record")

        # Overlay configs are JSON documents, not normalized asset relations.
        # Inspect every preset in the owning workspace before soft deletion so
        # a Browser Source cannot silently lose its background or image layer.
        references = {str(item) for item in (url, key) if item}
        async with db.execute("SELECT config FROM overlays WHERE workspace_id=?", (workspace_id,)) as cursor:
            configs = await cursor.fetchall()
        for row in configs:
            raw_config = row[0]
            try:
                parsed_config = json.loads(raw_config) if isinstance(raw_config, str) else raw_config
            except (TypeError, ValueError, json.JSONDecodeError):
                # A malformed legacy preset cannot be parsed reliably; it also
                # cannot prove a reference, so preserve existing behavior while
                # avoiding a deletion crash.
                continue
            if _overlay_config_references_asset(parsed_config, references):
                raise ValueError("Asset is still referenced by an overlay configuration")
        await db.execute("UPDATE media_assets SET deleted_at=CURRENT_TIMESTAMP WHERE id=? AND workspace_id=?", (asset_id, workspace_id))
        await db.commit()
    return True


async def persist_challonge_identity(
    resolved: dict,
    *,
    locator_key: str,
    workspace_id: str | None = None,
) -> dict:
    """Persist a canonical identity and its input alias without changing an existing binding.

    This is identity-only storage. It does not fetch participants/matches or write
    any Hub workflow field.
    """
    account = str(resolved.get("provider_account_id") or "")
    if not account:
        raise ValueError("Challonge import requires an integration account binding.")
    community = str(resolved.get("subdomain") or "")
    tournament_id = str(resolved["provider_tournament_id"])
    safe_scope = community or "global"
    canonical_slug = f"challonge:{account}:{safe_scope}:{tournament_id}"
    raw_data = json.dumps({
        "id": tournament_id,
        "name": resolved.get("name") or f"Challonge {tournament_id}",
        "provider_state": resolved.get("state"),
        "format": resolved.get("format"),
        "url_slug": resolved.get("url_slug"),
        "events": [],
    })
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        if is_postgres():
            # No tournament row exists on first import, so row locking alone
            # cannot serialize duplicate aliases resolving to this identity.
            await db.execute("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", ("import:" + canonical_slug,))
        async with db.execute(
            """
            SELECT * FROM tournaments
            WHERE provider_type = 'challonge'
              AND (CAST(? AS TEXT) IS NULL OR workspace_id = ?)
              AND provider_account_id = ?
              AND COALESCE(provider_subdomain, '') = ?
              AND provider_tournament_id = ?
            LIMIT 1
            """,
            (workspace_id, workspace_id, account, community, tournament_id),
        ) as cursor:
            existing = await cursor.fetchone()
        if existing:
            tournament = dict(existing)
            slug = tournament["slug"]
        else:
            slug = canonical_slug
            await db.execute(
                """
                INSERT INTO tournaments (
                    slug, name, raw_data, provider_type, provider_tournament_id,
                    provider_subdomain, provider_account_id, workspace_id
                ) VALUES (?, ?, ?, 'challonge', ?, ?, ?, ?)
                """,
                (slug, resolved.get("name") or f"Challonge {tournament_id}", raw_data,
                 tournament_id, community or None, account, workspace_id),
            )
            tournament = {
                "slug": slug, "name": resolved.get("name") or f"Challonge {tournament_id}",
                "provider_type": "challonge", "provider_tournament_id": tournament_id,
                "provider_subdomain": community or None, "provider_account_id": account,
                "workspace_id": workspace_id,
            }
        await db.execute(
            """
            INSERT INTO provider_locator_aliases (
                provider_type, provider_account_id, community_id, locator_key,
                canonical_tournament_id, tournament_slug, resolved_at
            ) VALUES ('challonge', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(provider_type, provider_account_id, community_id, locator_key)
            DO UPDATE SET canonical_tournament_id = excluded.canonical_tournament_id,
                          tournament_slug = excluded.tournament_slug,
                          resolved_at = CURRENT_TIMESTAMP
            """,
            (account, community, locator_key, tournament_id, slug),
        )
        await db.commit()
    return tournament

async def set_tournament_sync_status(
    slug: str,
    ready: bool,
    error: str | None = None,
    workspace_id: str | None = None,
):
    """Record remote freshness without ever retaining provider credentials."""
    async with aiosqlite.connect(DB_PATH) as db:
        scope = " AND workspace_id = ?" if workspace_id else ""
        params = ("ready" if ready else "error", None if ready else (error or "Provider synchronization failed."), slug)
        if workspace_id:
            params += (workspace_id,)
        await db.execute(
            "UPDATE tournaments SET provider_sync_status = ?, provider_sync_error = ?, provider_last_synced_at = CURRENT_TIMESTAMP WHERE slug = ?" + scope,
            params,
        )
        await db.commit()


async def save_bracket_snapshot(
    tournament_slug: str,
    sets: list[dict],
    workspace_id: str | None = None,
) -> None:
    """Persist the provider-normalized bracket for local-only dashboard reads."""
    async with aiosqlite.connect(DB_PATH) as db:
        if workspace_id:
            owned = await (await db.execute(
                "SELECT 1 FROM tournaments WHERE slug = ? AND workspace_id = ?",
                (tournament_slug, workspace_id),
            )).fetchone()
            if not owned:
                raise ValueError("Tournament is not owned by the requested workspace")
        await db.execute(
            """
            INSERT INTO provider_bracket_snapshots (tournament_slug, sets_json, synced_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tournament_slug) DO UPDATE SET
                sets_json = excluded.sets_json, synced_at = CURRENT_TIMESTAMP
            """,
            (tournament_slug, json.dumps(sets)),
        )
        await db.commit()


async def get_bracket_snapshot(
    tournament_slug: str,
    workspace_id: str | None = None,
) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT s.sets_json, s.synced_at
            FROM provider_bracket_snapshots s
            JOIN tournaments t ON t.slug = s.tournament_slug
            WHERE s.tournament_slug = ?
        """
        params: tuple[str, ...] = (tournament_slug,)
        if workspace_id:
            query += " AND t.workspace_id = ?"
            params += (workspace_id,)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
    if not row:
        return {"sets": [], "synced_at": None}
    try:
        sets = json.loads(row["sets_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        sets = []
    return {"sets": sets if isinstance(sets, list) else [], "synced_at": row["synced_at"]}


class StaleProviderSnapshotError(ValueError):
    """A provider observation must not overwrite a newer durable projection."""


def _revision_is_older(candidate: str | None, existing: str | None) -> bool:
    if not candidate or not existing or candidate == existing:
        return False
    if candidate.isdigit() and existing.isdigit():
        return int(candidate) < int(existing)
    # ISO timestamps are lexically sortable; opaque revisions are intentionally
    # not guessed at and therefore need a later provider-specific policy.
    if "T" in candidate and "T" in existing:
        return candidate < existing
    return False


async def apply_challonge_snapshot(
    tournament_slug: str,
    provider_account_id: str,
    provider_sets: list[ProviderSet],
    participants: list[ProviderEntrant],
    *,
    scope: str,
    revision: str | None,
    observed_at: str | None,
    covered_scopes: set[str],
    complete_pages: bool,
) -> dict:
    """Atomically publish one complete, read-only Challonge projection.

    This deliberately writes provider fields only.  It never repairs legacy
    status, changes a station/stream, or dispatches a Discord/Completion effect.
    Partial scopes update the rows they contain and never infer absence elsewhere.
    """
    if not complete_pages:
        raise ValueError("A partial Challonge page set cannot be published as a snapshot.")
    if any(not item.id or not item.provider_set_id for item in provider_sets):
        raise ValueError("Mapped Challonge snapshot contains an invalid match identifier.")
    if len({item.id for item in provider_sets}) != len(provider_sets):
        raise ValueError("Mapped Challonge snapshot contains duplicate match identifiers.")

    observed_at = observed_at or datetime.datetime.now(datetime.UTC).isoformat()
    serialized = [
        {
            "id": item.id, "provider_set_id": item.provider_set_id,
            "state": int(item.state), "provider_state_raw": item.provider_state_raw,
            "round": item.round_name, "fullRoundText": item.round_name,
            "identifier": item.identifier, "event_id": item.event_id,
            "event_name": item.event_name, "phaseGroup": {"displayIdentifier": item.phase_group},
            "p1": item.entrant1.name if item.entrant1 else "TBD",
            "p2": item.entrant2.name if item.entrant2 else "TBD",
            "p1_eid": item.entrant1.id if item.entrant1 else None,
            "p2_eid": item.entrant2.id if item.entrant2 else None,
        }
        for item in provider_sets
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT provider_type FROM tournaments WHERE slug = ?" + (" FOR UPDATE" if is_postgres() else ""), (tournament_slug,)
            ) as cursor:
                tournament = await cursor.fetchone()
            if not tournament or (tournament["provider_type"] or "startgg") != "challonge":
                raise ValueError("Tournament is not a stored Challonge tournament.")
            async with db.execute(
                "SELECT revision, payload_json FROM provider_snapshot_cache WHERE provider_type = 'challonge' AND provider_account_id = ? AND tournament_slug = ? AND scope = 'full_snapshot'",
                (provider_account_id, tournament_slug),
            ) as cursor:
                previous = await cursor.fetchone()
            previous_revision = previous["revision"] if previous else None
            if _revision_is_older(revision, previous_revision):
                raise StaleProviderSnapshotError("A stale Challonge snapshot was rejected.")
            previous_payload = json.loads(previous["payload_json"] or "{}") if previous else {}
            sequence = int(previous_payload.get("observation_sequence") or 0) + 1

            for participant in participants:
                await db.execute(
                    """INSERT INTO provider_snapshot_participants (
                        provider_type, provider_account_id, tournament_slug,
                        provider_participant_id, display_name, observed_at
                    ) VALUES ('challonge', ?, ?, ?, ?, ?)
                    ON CONFLICT(provider_type, provider_account_id, tournament_slug, provider_participant_id)
                    DO UPDATE SET display_name = excluded.display_name, observed_at = excluded.observed_at""",
                    (provider_account_id, tournament_slug, participant.id, participant.name, observed_at),
                )

            for item in provider_sets:
                normalized = item.state.name.lower()
                async with db.execute(
                    "SELECT provider_revision, provider_observed_at FROM active_matches WHERE set_id = ?", (item.id,)
                ) as cursor:
                    existing = await cursor.fetchone()
                if existing and _revision_is_older(item.provider_revision, existing["provider_revision"]):
                    continue
                values = (
                    item.entrant1.name if item.entrant1 else "TBD", item.entrant2.name if item.entrant2 else "TBD",
                    item.entrant1.id if item.entrant1 else None, item.entrant2.id if item.entrant2 else None,
                    item.round_name, item.identifier, item.phase_group, item.event_id, item.event_name,
                    item.provider_set_id, item.provider_state_raw, normalized, item.provider_revision,
                    observed_at, "synced", observed_at, item.id,
                )
                if existing:
                    await db.execute(
                        """UPDATE active_matches SET p1_name=?, p2_name=?, p1_entrant_id=?, p2_entrant_id=?,
                           round_name=?, match_number=?, phase_group=?, event_id=?, event_name=?,
                           provider_set_id=?, provider_state_raw=?, provider_state_normalized=?,
                           provider_revision=?, provider_observed_at=?, sync_status=?,
                           last_successful_snapshot_at=? WHERE set_id=?""",
                        values,
                    )
                else:
                    await db.execute(
                        """INSERT INTO active_matches (
                           set_id, tournament_slug, event_id, event_name, p1_name, p2_name,
                           p1_entrant_id, p2_entrant_id, round_name, match_number, phase_group,
                           status, is_stream_match, provider_set_id, provider_state_raw,
                           provider_state_normalized, provider_revision, provider_observed_at,
                           hub_status, hub_status_origin, sync_status, last_successful_snapshot_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_started', FALSE, ?, ?, ?, ?, ?,
                           'not_started', 'provider_sync', 'synced', ?)""",
                        (
                            item.id, tournament_slug, item.event_id, item.event_name,
                            item.entrant1.name if item.entrant1 else "TBD", item.entrant2.name if item.entrant2 else "TBD",
                            item.entrant1.id if item.entrant1 else None, item.entrant2.id if item.entrant2 else None,
                            item.round_name, item.identifier, item.phase_group, item.provider_set_id,
                            item.provider_state_raw, normalized, item.provider_revision, observed_at, observed_at,
                        ),
                    )

            payload = {"observation_sequence": sequence, "complete_pages": True}
            coverage = json.dumps(sorted(covered_scopes))
            await db.execute(
                """INSERT INTO provider_snapshot_cache (
                    provider_type, provider_account_id, tournament_slug, scope,
                    entity_coverage_json, revision, payload_json
                ) VALUES ('challonge', ?, ?, 'full_snapshot', ?, ?, ?)
                ON CONFLICT(provider_type, provider_account_id, tournament_slug, scope)
                DO UPDATE SET entity_coverage_json=excluded.entity_coverage_json,
                              revision=excluded.revision, payload_json=excluded.payload_json,
                              updated_at=CURRENT_TIMESTAMP""",
                (provider_account_id, tournament_slug, coverage, revision, json.dumps(payload)),
            )
            await db.execute(
                """INSERT INTO provider_bracket_snapshots (tournament_slug, sets_json, synced_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(tournament_slug) DO UPDATE SET sets_json=excluded.sets_json, synced_at=CURRENT_TIMESTAMP""",
                (tournament_slug, json.dumps(serialized)),
            )
            await db.execute(
                """UPDATE tournaments SET provider_sync_status='ready', provider_sync_error=NULL,
                   provider_last_synced_at=CURRENT_TIMESTAMP WHERE slug=?""", (tournament_slug,)
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return {"sets": serialized, "observation_sequence": sequence}


async def record_provider_api_usage(provider_type: str, method: str, path: str, status_code: int | None,
                                    *, workspace_id: str | None = None,
                                    provider_account_id: str | None = None) -> None:
    """Record one outgoing provider request without retaining credentials or payloads."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO provider_api_usage
               (provider_type, provider_account_id, workspace_id, method, path, status_code)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (provider_type, provider_account_id, workspace_id, method.upper(), path.split("?", 1)[0], status_code),
        )
        await db.commit()


async def get_provider_usage(provider_type: str, monthly_limit: int | None = None,
                             *, workspace_id: str | None = None,
                             provider_account_id: str | None = None) -> dict:
    """Return a local month-to-date request count for the quota badge."""
    # ``date('now', ...)`` is SQLite-only and silently breaks the PostgreSQL
    # runtime path. Keep the predicate dialect-specific while retaining the
    # same UTC month boundary for both stores.
    month_start = (
        "date_trunc('month', CURRENT_TIMESTAMP)" if is_postgres()
        else "datetime('now', 'start of month')"
    )
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            f"""
            SELECT COUNT(*) FROM provider_api_usage
            WHERE provider_type = ?
              AND (CAST(? AS TEXT) IS NULL OR workspace_id = ?)
              AND (CAST(? AS TEXT) IS NULL OR provider_account_id = ?)
              AND created_at >= {month_start}
            """,
            (provider_type, workspace_id, workspace_id, provider_account_id, provider_account_id),
        ) as cursor:
            used = int((await cursor.fetchone())[0])
    return {
        "used": used,
        "limit": monthly_limit,
        "remaining": max(0, monthly_limit - used) if monthly_limit is not None else None,
        "estimated": True,
    }

async def delete_tournament(slug: str, workspace_id: str | None = None):
    """Remove one tournament's local projection without touching its provider.

    Physical stations are global, so an active match blocks removal rather than
    silently disconnecting a real setup.  Once the tournament is inactive, its
    completed/local data is removed atomically and any stale station ownership
    belonging to one of its matches is released.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        match_scope = " AND workspace_id = ?" if workspace_id is not None else ""
        match_params = (slug, workspace_id) if workspace_id is not None else (slug,)
        if workspace_id is not None:
            owned = await (await db.execute(
                "SELECT 1 FROM tournaments WHERE slug = ? AND workspace_id = ?", (slug, workspace_id)
            )).fetchone()
            if not owned:
                raise ValueError("Tournament not found in workspace")
        async with db.execute(
            """SELECT set_id, p1_name, p2_name FROM active_matches
               WHERE tournament_slug = ?""" + match_scope + """
                 AND (status IN ('not_started', 'called', 'in_progress')
                      OR hub_status IN ('not_started', 'called', 'ready', 'in_progress'))
               LIMIT 1""",
            match_params,
        ) as cursor:
            active = await cursor.fetchone()
        if active:
            raise TournamentRemovalBlocked(
                f"Tournament has an active match ({active['p1_name'] or 'Player 1'} vs "
                f"{active['p2_name'] or 'Player 2'}). Complete, unassign, or reset it before removal."
            )

        await db.execute("BEGIN IMMEDIATE")
        try:
            # Only clear a physical station if it explicitly names a match that
            # belongs to this tournament.  Never release another tournament's
            # station just because a stale local row has a matching station_id.
            await db.execute(
                """UPDATE stations SET active_match_id = NULL, active_overlay = NULL
                   WHERE active_match_id IN (
                     SELECT set_id FROM active_matches WHERE tournament_slug = ?""" + match_scope + """
                   )""",
                match_params,
            )
            scoped_match_subquery = "(SELECT set_id FROM active_matches WHERE tournament_slug = ?" + match_scope + ")"
            outbox_query = "DELETE FROM workflow_outbox WHERE match_id IN " + scoped_match_subquery
            outbox_params: list = list(match_params)
            if workspace_id is not None:
                outbox_query += " AND workspace_id = ?"
                outbox_params.append(workspace_id)
            await db.execute(outbox_query, outbox_params)
            ledger_query = "DELETE FROM provider_command_ledger WHERE tournament_slug = ?"
            ledger_params: list = [slug]
            if workspace_id is not None:
                ledger_query += " AND workspace_id = ?"
                ledger_params.append(workspace_id)
            await db.execute(ledger_query, ledger_params)
            await db.execute("DELETE FROM conflicts WHERE set_id IN " + scoped_match_subquery, match_params)
            workspace_tables = {"planned_streams", "tournament_player_links", "provider_identity_links", "provider_snapshot_cache"}
            for table in ("planned_streams", "match_results", "tournament_player_links", "provider_bracket_snapshots", "provider_reconciliation_audit", "provider_identity_links", "provider_snapshot_cache", "provider_locator_aliases", "provider_snapshot_participants", "provider_request_telemetry"):
                query = f"DELETE FROM {table} WHERE tournament_slug = ?"
                params: list = [slug]
                if workspace_id is not None and table in workspace_tables:
                    query += " AND workspace_id = ?"
                    params.append(workspace_id)
                await db.execute(query, params)
            query = "DELETE FROM active_matches WHERE tournament_slug = ?" + match_scope
            await db.execute(query, match_params)
            query = "DELETE FROM tournaments WHERE slug = ?"
            params: list = [slug]
            if workspace_id is not None:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            await db.execute(query, params)
        except Exception:
            await db.rollback()
            raise
        await db.commit()


async def set_tournament_streams(slug: str, streams: list, workspace_id: str | None = None):
    """Persist the start.gg stream list for a tournament as JSON.

    `streams` is a list of dicts with keys: id, name, source, game.
    """
    payload = json.dumps(streams or [])
    async with aiosqlite.connect(DB_PATH) as db:
        query = "UPDATE tournaments SET streams_json = ? WHERE slug = ?"
        params: list = [payload, slug]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        await db.execute(query, params)
        await db.commit()


async def get_tournament_streams(slug: str, workspace_id: str | None = None) -> list:
    """Return the cached start.gg stream list for a tournament."""
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT streams_json FROM tournaments WHERE slug = ?"
        params: list = [slug]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
    if not row or not row[0]:
        return []
    try:
        return json.loads(row[0])
    except Exception:
        return []


async def get_station_stream_id(station_id: str, workspace_id: str | None = None) -> str | None:
    """Return the start.gg streamId mapped to a local station, or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        query, params = "SELECT startgg_stream_id FROM stations WHERE (id = ? OR public_id = ?)", (station_id, station_id)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params += (workspace_id,)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
    return (row[0] if row else None) or None


async def get_station_by_stream_id(stream_id: str, workspace_id: str | None = None) -> dict | None:
    """Find the local station mapped to a given start.gg streamId, or None."""
    if not stream_id:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query, params = "SELECT * FROM stations WHERE startgg_stream_id = ?", [stream_id]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        query += " LIMIT 1"
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


# ── Planned Streams ──────────────────────────────────────────────────────
async def add_planned_stream(set_id: str, tournament_slug: str,
                             stream_id: str | None = None, note: str | None = None,
                             workspace_id: str | None = None):
    """Mark a (potentially preview) set for inclusion on stream once it goes live."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO planned_streams (set_id, tournament_slug, stream_id, note, workspace_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(set_id) DO UPDATE SET
                tournament_slug=excluded.tournament_slug,
                stream_id=excluded.stream_id,
                note=excluded.note,
                workspace_id=excluded.workspace_id
        ''', (set_id, tournament_slug, stream_id, note, workspace_id))
        await db.commit()


async def remove_planned_stream(set_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query, params = "DELETE FROM planned_streams WHERE set_id = ?", [set_id]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        await db.execute(query, params)
        await db.commit()


async def list_planned_streams(tournament_slug: str | None = None, workspace_id: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        filters, args = [], []
        if tournament_slug:
            filters.append("tournament_slug = ?")
            args.append(tournament_slug)
        if workspace_id is not None:
            filters.append("workspace_id = ?")
            args.append(workspace_id)
        q = "SELECT * FROM planned_streams"
        if filters:
            q += " WHERE " + " AND ".join(filters)
        q += " ORDER BY created_at DESC"
        async with db.execute(q, args) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_planned_stream(set_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM planned_streams WHERE set_id = ?", (set_id,)) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


# ── Pending Bio-Code Verifications ──────────────────────────────────────
import datetime as _dt


async def create_pending_verification(discord_id: str, startgg_slug: str,
                                       code: str, ttl_seconds: int = 300,
                                       workspace_id: str | None = None):
    """Create or replace a pending bio-code verification for this Discord user."""
    expires = (_dt.datetime.utcnow() + _dt.timedelta(seconds=ttl_seconds)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO pending_verifications (discord_id, workspace_id, startgg_slug, code, expires_at, attempts) "
            "VALUES (?, ?, ?, ?, ?, 0) "
            "ON CONFLICT(discord_id) DO UPDATE SET "
            "  workspace_id=excluded.workspace_id, startgg_slug=excluded.startgg_slug, code=excluded.code, "
            "  expires_at=excluded.expires_at, attempts=0, created_at=CURRENT_TIMESTAMP",
            (discord_id, workspace_id, startgg_slug, code, expires)
        )
        await db.commit()


async def get_pending_verification(discord_id: str, workspace_id: str | None = None) -> dict | None:
    """Return the pending verification, or None if missing/expired."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM pending_verifications WHERE discord_id = ?"
        params: tuple[str, ...] = (discord_id,)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params += (workspace_id,)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        from backend.core.timestamps import as_utc
        expires = as_utc(d["expires_at"])
        if _dt.datetime.now(_dt.timezone.utc) > expires:
            return None
    except Exception:
        return None
    return d


async def increment_verification_attempts(discord_id: str, workspace_id: str | None = None) -> int:
    """Increment attempts counter; return new value. Used to rate-limit retries."""
    async with aiosqlite.connect(DB_PATH) as db:
        query = "UPDATE pending_verifications SET attempts = attempts + 1 WHERE discord_id = ?"
        params: tuple[str, ...] = (discord_id,)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params += (workspace_id,)
        await db.execute(query, params)
        await db.commit()
        query = "SELECT attempts FROM pending_verifications WHERE discord_id = ?"
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params += (workspace_id,)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def delete_pending_verification(discord_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query = "DELETE FROM pending_verifications WHERE discord_id = ?"
        params: tuple[str, ...] = (discord_id,)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params += (workspace_id,)
        await db.execute(query, params)
        await db.commit()

# ── Match Results ──────────────────────────────────────────────────────────
async def save_match_result(set_id: str, tournament_slug: str, stream_slot: str,
                            p1_name: str, p2_name: str, winner: str,
                            p1_score: str, p2_score: str, round_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO match_results
                (set_id, tournament_slug, stream_slot, p1_name, p2_name, winner, p1_score, p2_score, round_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (set_id, tournament_slug, stream_slot, p1_name, p2_name, winner, p1_score, p2_score, round_name))
        await db.commit()

async def get_match_results(tournament_slug: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if tournament_slug:
            async with db.execute("SELECT * FROM match_results WHERE tournament_slug = ? ORDER BY created_at DESC", (tournament_slug,)) as cursor:
                return [dict(r) for r in await cursor.fetchall()]
        async with db.execute("SELECT * FROM match_results ORDER BY created_at DESC LIMIT 100") as cursor:
            return [dict(r) for r in await cursor.fetchall()]

# ── Stations ───────────────────────────────────────────────────────────────
def _station_public(row: dict) -> dict:
    result = dict(row)
    result["storage_id"] = result["id"]
    result["id"] = result.get("public_id") or result["id"]
    return result


async def _station_storage_id(db, station_id: str, workspace_id: str | None) -> str | None:
    query = "SELECT id FROM stations WHERE (id=? OR public_id=?)"
    params: tuple = (station_id, station_id)
    if workspace_id is not None:
        query += " AND workspace_id=?"
        params += (workspace_id,)
    row = await (await db.execute(query, params)).fetchone()
    return str(row[0]) if row else None


async def get_stations(workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query, params = "SELECT * FROM stations", ()
        if workspace_id is not None:
            query, params = query + " WHERE workspace_id=?", (workspace_id,)
        async with db.execute(query + " ORDER BY id", params) as cursor:
            return [_station_public(dict(r)) for r in await cursor.fetchall()]

async def get_station(station_id: str, workspace_id: str | None = None) -> dict | None:
    """Single station row (incl. is_stream_station / room_* / event_id), or None."""
    if not station_id:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        storage_id = await _station_storage_id(db, station_id, workspace_id)
        if storage_id is None:
            return None
        async with db.execute("SELECT * FROM stations WHERE id = ?", (storage_id,)) as cursor:
            row = await cursor.fetchone()
            return _station_public(dict(row)) if row else None

async def create_station(station_id: str, name: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        collision = await (await db.execute("SELECT 1 FROM stations WHERE id=?", (station_id,))).fetchone()
        storage_id = station_id if not collision else f"{workspace_id}:{station_id}"
        await db.execute(
            "INSERT INTO stations (id, public_id, name, workspace_id) VALUES (?, ?, ?, ?)",
            (storage_id, station_id, name, workspace_id),
        )
        await db.commit()

async def update_station(station_id: str, workspace_id: str | None = None, **kwargs):
    if not kwargs:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        valid_cols = []
        async with db.execute("PRAGMA table_info(stations)") as cursor:
            info = await cursor.fetchall()
            valid_cols = [row[1] for row in info]

        filtered_kwargs = {k: _database_value(k, v) for k, v in kwargs.items() if k in valid_cols}
        if not filtered_kwargs:
            return

        set_clause = ', '.join([f"{k} = ?" for k in filtered_kwargs.keys()])
        storage_id = await _station_storage_id(db, station_id, workspace_id)
        if storage_id is None:
            raise ValueError("Station not found in workspace")
        values = list(filtered_kwargs.values()) + [storage_id]
        await db.execute(f"UPDATE stations SET {set_clause} WHERE id = ?", values)
        await db.commit()

async def update_station_active_overlay(station_id: str, overlay_name: str | None, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        # Browser Source URLs and API routes use a stable public station id.
        # A colliding id in another workspace is stored internally as
        # ``<workspace>:<public-id>``, so resolve it inside this connection
        # before mutating.  Do not let an unqualified public id silently miss
        # its own station or update a sibling workspace's row.
        storage_id = await _station_storage_id(db, station_id, workspace_id)
        if storage_id is None:
            raise ValueError("Station not found in workspace")
        await db.execute("UPDATE stations SET active_overlay = ? WHERE id = ?", (overlay_name, storage_id))
        await db.commit()

async def get_station_active_overlay(station_id: str, workspace_id: str | None = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        storage_id = await _station_storage_id(db, station_id, workspace_id)
        if storage_id is None:
            return None
        async with db.execute("SELECT active_overlay FROM stations WHERE id = ?", (storage_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def delete_station(station_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        storage_id = await _station_storage_id(db, station_id, workspace_id)
        if storage_id is None:
            raise ValueError("Station not found in workspace")
        await db.execute("DELETE FROM station_overlays WHERE station_id = ?", (storage_id,))
        await db.execute("DELETE FROM stations WHERE id = ?", (storage_id,))
        await db.commit()

# ── Station Overlays ───────────────────────────────────────────────────────
async def get_all_station_overlays(workspace_id: str | None = None):
    """Fetch all station overlays in one query (avoids N+1 when listing stations)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT so.* FROM station_overlays so JOIN stations s ON s.id=so.station_id"
        params: tuple = ()
        if workspace_id is not None:
            query += " WHERE s.workspace_id=?"
            params = (workspace_id,)
        async with db.execute(query + " ORDER BY so.station_id, so.sort_order", params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def get_station_overlays(station_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        storage_id = await _station_storage_id(db, station_id, workspace_id)
        if storage_id is None:
            return []
        async with db.execute(
            "SELECT so.* FROM station_overlays so WHERE so.station_id = ? ORDER BY sort_order",
            (storage_id,),
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def add_station_overlay(station_id: str, overlay_name: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        storage_id = await _station_storage_id(db, station_id, workspace_id)
        if storage_id is None:
            raise PermissionError("Station belongs to another workspace")
        async with db.execute(
            "SELECT MAX(sort_order) FROM station_overlays WHERE station_id = ?", (storage_id,)
        ) as c:
            row = await c.fetchone()
            next_order = (row[0] or 0) + 1
        await db.execute(
            "INSERT INTO station_overlays (station_id, overlay_name, sort_order) VALUES (?, ?, ?)",
            (storage_id, overlay_name, next_order)
        )
        await db.commit()

async def remove_station_overlay(station_id: str, overlay_name: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        storage_id = await _station_storage_id(db, station_id, workspace_id)
        if storage_id is None:
            raise PermissionError("Station belongs to another workspace")
        await db.execute(
            "DELETE FROM station_overlays WHERE station_id = ? AND overlay_name = ?",
            (storage_id, overlay_name),
        )
        await db.commit()

# ── Active Matches ─────────────────────────────────────────────────────────
async def assign_station_to_active_match(
    set_id: str, station_id: str, workspace_id: str | None = None,
) -> bool:
    """Fast targeted station update, scoped when a trusted workspace is known.

    ``set_id`` is still a legacy physical key on upgraded installations.  New
    runtime callers must pass their trusted workspace so this helper remains
    safe when the schema is upgraded to allow the same provider set in more
    than one tenant.  Omitting the scope is retained only for historical local
    maintenance callers.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        scope = " AND workspace_id = ?" if workspace_id is not None else ""
        async with db.execute(
            "UPDATE active_matches SET station_id = ? WHERE set_id = ?" + scope,
            (station_id, set_id) + ((workspace_id,) if workspace_id is not None else ())
        ) as cursor:
            await db.commit()
            return cursor.rowcount > 0

async def get_used_station_ids(exclude_set_id: str, workspace_id: str | None = None) -> set:
    """Station IDs currently occupied by other active (not-completed) matches."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT station_id
            FROM active_matches
            WHERE station_id IS NOT NULL
              AND status IN ('not_started', 'called', 'in_progress')
              AND set_id != ?
            """ + (" AND workspace_id = ?" if workspace_id is not None else ""),
            (exclude_set_id,) + ((workspace_id,) if workspace_id is not None else ())
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

async def get_active_matches(tournament_slug: str = None, event_id: str = None, workspace_id: str | None = None):
    """List active matches, optionally scoped to a tournament and/or event.

    Event scoping prevents cross-game contamination in multi-event tournaments:
    the hub passes the selected event_id so only that game's matches surface.
    """
    clauses, params = [], []
    if tournament_slug:
        clauses.append("active_matches.tournament_slug = ?")
        params.append(tournament_slug)
    if event_id is not None:
        clauses.append("active_matches.event_id = ?")
        params.append(str(event_id))
    if workspace_id is not None:
        clauses.append("active_matches.workspace_id = ?")
        params.append(workspace_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""SELECT active_matches.*, COALESCE(tournaments.provider_type, 'startgg') AS provider_type
                FROM active_matches LEFT JOIN tournaments ON tournaments.slug = active_matches.tournament_slug
                  AND (active_matches.workspace_id IS NULL OR tournaments.workspace_id = active_matches.workspace_id)
                {where} ORDER BY active_matches.created_at""", params
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


def serialize_active_match_for_display(match: dict) -> dict:
    """Add the provider-neutral display projection without persisting a change.

    This is deliberately a serializer rather than a workflow helper: callers
    receive a fresh dictionary and the SQLite row, station ownership, Discord
    workflow, and provider state remain untouched.
    """
    from datetime import date, datetime

    from backend.core.tournament_progression import project_match

    def json_safe(value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [json_safe(item) for item in value]
        return value

    # psycopg returns TIMESTAMP/TIMESTAMPTZ columns as datetime instances,
    # while the public display contract is string-based. Normalize both the
    # persisted row and the derived Discord/provider projection without
    # changing storage or workflow state.
    return json_safe({**match, **project_match(match)})

async def get_active_match(set_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query, params = "SELECT * FROM active_matches WHERE set_id = ?", (set_id,)
        if workspace_id is not None:
            query, params = query + " AND workspace_id=?", params + (workspace_id,)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_active_match_by_thread(discord_thread_id: str, workspace_id: str | None = None):
    """Resolve the active match owning a Discord match thread.

    The AI referee receives a thread/channel id, not a start.gg set id. Looking
    the match up by discord_thread_id is the reliable bridge back to the real
    set_id + player Discord IDs (fixes the winner-mapping mismatch).
    """
    if not discord_thread_id:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query, params = "SELECT * FROM active_matches WHERE discord_thread_id = ?", [str(discord_thread_id)]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_active_matches_by_set_ids(set_ids: list[str], workspace_id: str | None = None) -> list[dict]:
    """Batch-fetch active matches for many set_ids in one query (avoids N+1)."""
    if not set_ids:
        return []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ','.join('?' * len(set_ids))
        query = f"SELECT am.* FROM active_matches am WHERE am.set_id IN ({placeholders})"
        params: list = list(set_ids)
        if workspace_id is not None:
            query += " AND am.workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def get_match_occupying_station(station_id: str, exclude_set_id: str = None, workspace_id: str | None = None) -> dict | None:
    query = """
        SELECT * FROM active_matches 
        WHERE station_id = ? 
          AND status IN ('not_started', 'called', 'in_progress')
    """
    params = [station_id]
    if exclude_set_id:
        query += " AND set_id != ?"
        params.append(exclude_set_id)
    if workspace_id is not None:
        query += " AND workspace_id = ?"
        params.append(workspace_id)
        
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def upsert_active_match(set_id: str, workspace_id: str | None = None, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        # Get valid columns
        valid_cols = []
        async with db.execute("PRAGMA table_info(active_matches)") as cursor:
            info = await cursor.fetchall()
            valid_cols = [row[1] for row in info]
        
        # Filter kwargs
        if workspace_id is not None and "workspace_id" in valid_cols:
            kwargs["workspace_id"] = workspace_id
        filtered_kwargs = {k: _database_value(k, v) for k, v in kwargs.items() if k in valid_cols}
        
        existing = None
        query = "SELECT set_id FROM active_matches WHERE set_id = ?"
        params: tuple = (set_id,)
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params += (workspace_id,)
        async with db.execute(query, params) as c:
            existing = await c.fetchone()

        if existing:
            if filtered_kwargs:
                set_clause = ', '.join([f'"{k}" = ?' for k in filtered_kwargs.keys()])
                values = list(filtered_kwargs.values()) + [set_id]
                where = "set_id = ?"
                if workspace_id is not None:
                    where += " AND workspace_id = ?"
                    values.append(workspace_id)
                await db.execute(f'UPDATE active_matches SET {set_clause} WHERE {where}', values)
        else:
            filtered_kwargs['set_id'] = set_id
            cols = ', '.join([f'"{k}"' for k in filtered_kwargs.keys()])
            placeholders = ', '.join(['?'] * len(filtered_kwargs))
            await db.execute(f"INSERT INTO active_matches ({cols}) VALUES ({placeholders})", list(filtered_kwargs.values()))
        await db.commit()

async def delete_active_match(set_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query, params = "DELETE FROM active_matches WHERE set_id = ?", [set_id]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        await db.execute(query, params)
        await db.commit()


# ── Start.gg ActivityState integer → local status ────────────────────────────────
# Canonical state mapping from ProviderSetState to local DB status
_PROVIDER_STATE_TO_LOCAL = {
    ProviderSetState.NOT_STARTED:  'not_started',
    ProviderSetState.CALLED:       'called',
    ProviderSetState.IN_PROGRESS:  'in_progress',
    ProviderSetState.COMPLETE:     'complete',
    ProviderSetState.QUEUED:       'not_started',
}

_TERMINAL_STATES = {ProviderSetState.COMPLETE}
_AUTO_ADD_STATES = {
    ProviderSetState.NOT_STARTED,
    ProviderSetState.IN_PROGRESS,
    ProviderSetState.CALLED,
    ProviderSetState.QUEUED,
}


async def _preload_sync_data(db, tournament_slug: str, workspace_id: str | None = None):
    scope = " AND workspace_id = ?" if workspace_id is not None else ""
    scope_params = (workspace_id,) if workspace_id is not None else ()
    async with db.execute(
        "SELECT bot_manage_limit, check_in_source FROM tournaments WHERE slug = ?" + scope,
        (tournament_slug,) + scope_params,
    ) as t_cursor:
        t_row = await t_cursor.fetchone()
        bot_manage_limit = t_row[0] if t_row else "off"
        check_in_source = (t_row[1] if t_row and t_row[1] else "discord")

    async with db.execute("SELECT set_id, status FROM active_matches WHERE tournament_slug = ?" + scope, (tournament_slug,) + scope_params) as cursor:
        rows = await cursor.fetchall()
        local_matches = {row[0]: row[1] for row in rows}

    async with db.execute(
        "SELECT set_id, stream_id FROM planned_streams WHERE tournament_slug = ?" + scope,
        (tournament_slug,) + scope_params
    ) as cursor:
        planned = {row[0]: row[1] for row in await cursor.fetchall()}

    async with db.execute(
        "SELECT id, startgg_stream_id FROM stations WHERE startgg_stream_id IS NOT NULL AND startgg_stream_id != ''"
        + (" AND workspace_id = ?" if workspace_id is not None else ""), scope_params
    ) as cursor:
        station_by_stream = {row[1]: row[0] for row in await cursor.fetchall()}

    async with db.execute(
        "SELECT startgg_id, discord_id FROM players WHERE startgg_id IS NOT NULL AND startgg_id != ''"
        + (" AND workspace_id = ?" if workspace_id is not None else ""), scope_params
    ) as cursor:
        discord_by_startgg = {str(row[0]): str(row[1]) for row in await cursor.fetchall()}

    # Player-uploaded broadcast avatars (Cloudinary/local URL), keyed by start.gg
    # user id. These OVERRIDE the low-quality start.gg profile picture on overlays.
    async with db.execute(
        "SELECT startgg_id, avatar_path FROM players "
        "WHERE startgg_id IS NOT NULL AND startgg_id != '' "
        "AND avatar_path IS NOT NULL AND avatar_path != ''"
        + (" AND workspace_id = ?" if workspace_id is not None else ""), scope_params
    ) as cursor:
        avatar_by_startgg = {str(row[0]): str(row[1]) for row in await cursor.fetchall()}

    async with db.execute(
        """SELECT l.entrant_id, l.player_discord_id, p.avatar_path
           FROM tournament_player_links l
           LEFT JOIN players p ON p.discord_id = l.player_discord_id
           WHERE l.tournament_slug = ?""" + (" AND l.workspace_id = ?" if workspace_id is not None else ""),
        (tournament_slug,) + scope_params,
    ) as cursor:
        explicit_links = {
            str(row[0]): {"discord_id": str(row[1]), "avatar_path": row[2]}
            for row in await cursor.fetchall()
        }

    return bot_manage_limit, check_in_source, local_matches, planned, station_by_stream, discord_by_startgg, avatar_by_startgg, explicit_links

async def _update_existing_match(
    db, sid, ps, local_status, provider_status, planned, station_by_stream, discord_by_startgg,
    p1_name, p2_name, p1_avatar, p2_avatar, p1_eid, p2_eid, round_name, match_num, phase_group,
    check_in_source='discord', explicit_links=None, workspace_id: str | None = None,
):
    """Reconcile one existing match against the provider state. Returns a list of hub
    commands the CALLER must enqueue AFTER commit (enqueuing mid-transaction would risk a
    SQLite write-lock against this still-open connection)."""
    pending_cmds: list[str] = []

    if ps.state in _TERMINAL_STATES:
        new_status = 'complete'
    elif ps.state == ProviderSetState.NOT_STARTED and local_status in ('complete', 'dq'):
        new_status = 'not_started'
    elif check_in_source == 'startgg' and local_status == 'called' and ps.state == ProviderSetState.IN_PROGRESS:
        # start.gg-mode check-in: players checked in on start.gg → the set went ACTIVE.
        # The bot has no I'm-Ready buttons in this mode, so the poll drives the advance.
        new_status = 'in_progress'
    elif provider_status and local_status == 'not_started':
        new_status = provider_status
    else:
        new_status = local_status

    # Bracket reset on the provider drops a set back to NOT_STARTED — wipe any
    # stale local scores during sync so the row mirrors the clean provider state.
    reset_scores = new_status == 'not_started'

    uid1 = ps.entrant1.user_id if ps.entrant1 else None
    explicit_links = explicit_links or {}
    p1_link = explicit_links.get(str(p1_eid))
    p1_discord = p1_link["discord_id"] if p1_link else (discord_by_startgg.get(str(uid1)) if uid1 else None)
    uid2 = ps.entrant2.user_id if ps.entrant2 else None
    p2_link = explicit_links.get(str(p2_eid))
    p2_discord = p2_link["discord_id"] if p2_link else (discord_by_startgg.get(str(uid2)) if uid2 else None)

    match_scope = " AND workspace_id = ?" if workspace_id is not None else ""
    match_scope_params = (workspace_id,) if workspace_id is not None else ()
    await db.execute(f"""
        UPDATE active_matches SET
            p1_name=?, p2_name=?, p1_avatar=?, p2_avatar=?,
            p1_entrant_id=COALESCE(NULLIF(p1_entrant_id,''), ?),
            p2_entrant_id=COALESCE(NULLIF(p2_entrant_id,''), ?),
            p1_discord=COALESCE(NULLIF(p1_discord,''), ?),
            p2_discord=COALESCE(NULLIF(p2_discord,''), ?),
            round_name=?, match_number=?, phase_group=?,
            event_id=?, event_name=?, status=?{', p1_score = 0, p2_score = 0' if reset_scores else ''}
        WHERE set_id=?{match_scope}
    """, (p1_name, p2_name, p1_avatar, p2_avatar,
           p1_eid, p2_eid,
           p1_discord, p2_discord,
           round_name, match_num, str(phase_group),
           ps.event_id or "", ps.event_name or "", new_status, sid) + match_scope_params)

    if sid in planned:
        preferred_stream = planned.get(sid)
        if preferred_stream and preferred_stream in station_by_stream:
            await db.execute(
                "UPDATE active_matches SET is_stream_match = TRUE, "
                "station_id = COALESCE(station_id, ?) WHERE set_id = ?" + match_scope,
                (station_by_stream[preferred_stream], sid) + match_scope_params
            )
        else:
            await db.execute(
                "UPDATE active_matches SET is_stream_match = TRUE WHERE set_id = ?" + match_scope,
                (sid,) + match_scope_params
            )

    # ── start.gg-mode edge-triggered side-effects ─────────────────────────
    # Fire ONLY on the tick where the status actually changes (edge), never on every
    # tick the provider sits in a state (level) — else we'd re-DM/re-archive repeatedly.
    # DB-level work happens here on the open connection; Discord work is handed to the bot.
    if check_in_source == 'startgg' and new_status != local_status:
        if local_status == 'called' and new_status == 'in_progress':
            await db.execute(
                "UPDATE active_matches SET started_at = ? WHERE set_id = ?" + match_scope,
                (datetime.datetime.utcnow().isoformat(), sid) + match_scope_params,
            )
            # The bot handler binds a stream station (if applicable) and DMs lobby creds.
            pending_cmds.append(f"startgg_go_live {sid}")
        elif new_status == 'complete' and local_status not in ('complete', 'dq'):
            # Free any bound stream station the instant the match resolves on start.gg.
            await db.execute(
                "UPDATE active_matches SET station_id = NULL WHERE set_id = ?" + match_scope, (sid,) + match_scope_params
            )
            # Pass the thread id explicitly so the archive still works even if a later
            # orphan-sweep deletes the row before the bot drains the command.
            async with db.execute(
                "SELECT discord_thread_id FROM active_matches WHERE set_id = ?" + match_scope, (sid,) + match_scope_params
            ) as c:
                row = await c.fetchone()
            thread_id = row[0] if row and row[0] else ""
            if thread_id:
                pending_cmds.append(f"startgg_finish {sid} {thread_id}")

    return pending_cmds

async def _insert_new_match(
    db, sid, ps, tournament_slug, bot_manage_limit, planned, station_by_stream, discord_by_startgg,
    p1_name, p2_name, p1_avatar, p2_avatar, p1_eid, p2_eid, round_name, match_num, phase_group, explicit_links=None,
    workspace_id: str | None = None,
):
    should_add = ps.state in _AUTO_ADD_STATES or sid in planned
    if should_add:
        new_status = _PROVIDER_STATE_TO_LOCAL.get(ps.state, 'not_started')
        bot_enabled = should_bot_manage_match(round_name, str(phase_group), bot_manage_limit)
        is_stream = sid in planned
        station_id = None
        if is_stream:
            preferred_stream = planned.get(sid)
            if preferred_stream and preferred_stream in station_by_stream:
                station_id = station_by_stream[preferred_stream]

        uid1 = ps.entrant1.user_id if ps.entrant1 else None
        explicit_links = explicit_links or {}
        p1_link = explicit_links.get(str(p1_eid))
        p1_discord = p1_link["discord_id"] if p1_link else (discord_by_startgg.get(str(uid1)) if uid1 else None)
        uid2 = ps.entrant2.user_id if ps.entrant2 else None
        p2_link = explicit_links.get(str(p2_eid))
        p2_discord = p2_link["discord_id"] if p2_link else (discord_by_startgg.get(str(uid2)) if uid2 else None)

        workspace_column = ", workspace_id" if workspace_id is not None else ""
        workspace_value = ", ?" if workspace_id is not None else ""
        await db.execute(f"""
            INSERT INTO active_matches (
                set_id, tournament_slug, event_id, event_name, p1_name, p2_name, p1_avatar, p2_avatar,
                p1_entrant_id, p2_entrant_id, p1_discord, p2_discord,
                round_name, match_number, phase_group,
                status, bot_enabled, is_stream_match, station_id, provider_set_id, provider_state{workspace_column}
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?{workspace_value})
        """, (sid, tournament_slug, ps.event_id or "", ps.event_name or "", p1_name, p2_name, p1_avatar, p2_avatar,
               p1_eid, p2_eid, p1_discord, p2_discord,
               round_name, match_num, str(phase_group),
               new_status, bot_enabled, is_stream, station_id, str(ps.id).split(":")[-1], str(ps.state)
               ) + ((workspace_id,) if workspace_id is not None else ()))

async def sync_active_matches(tournament_slug: str, provider_sets: list[ProviderSet], workspace_id: str | None = None):
    """
    Synchronizes local active_matches with provider-agnostic ProviderSet objects.
    Source of Truth: provider — provider complete state always wins for terminal states.
    Hub-only metadata (station, is_stream_match, scores) is preserved.
    Also promotes planned-stream entries: sets in planned_streams get
    is_stream_match=TRUE and (if a stream_id is set) a matching station assigned.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        bot_manage_limit, check_in_source, local_matches, planned, station_by_stream, discord_by_startgg, avatar_by_startgg, explicit_links = await _preload_sync_data(db, tournament_slug, workspace_id)

        found_sids = set()
        # Hub commands to enqueue AFTER commit (enqueuing mid-transaction risks a
        # SQLite write-lock against this open connection).
        pending_cmds: list[str] = []

        for ps in provider_sets:
            sid = ps.id
            found_sids.add(sid)

            if ps.state == ProviderSetState.INVALID:
                continue

            if str(sid).startswith("preview"):
                continue

            p1_name  = ps.entrant1.name if ps.entrant1 else "TBD"
            p2_name  = ps.entrant2.name if ps.entrant2 else "TBD"
            p1_avatar = ps.entrant1.avatar_url if ps.entrant1 else None
            p2_avatar = ps.entrant2.avatar_url if ps.entrant2 else None
            # Broadcast override: a player's uploaded avatar (Cloudinary/local URL)
            # wins over start.gg's low-res profile picture on the overlay.
            uid1 = ps.entrant1.user_id if ps.entrant1 else None
            uid2 = ps.entrant2.user_id if ps.entrant2 else None
            if uid1 and avatar_by_startgg.get(str(uid1)):
                p1_avatar = avatar_by_startgg[str(uid1)]
            if uid2 and avatar_by_startgg.get(str(uid2)):
                p2_avatar = avatar_by_startgg[str(uid2)]
            p1_eid   = ps.entrant1.id if ps.entrant1 else None
            p2_eid   = ps.entrant2.id if ps.entrant2 else None
            if p1_eid in explicit_links and explicit_links[p1_eid].get("avatar_path"):
                p1_avatar = explicit_links[p1_eid]["avatar_path"]
            if p2_eid in explicit_links and explicit_links[p2_eid].get("avatar_path"):
                p2_avatar = explicit_links[p2_eid]["avatar_path"]
            round_name  = ps.round_name
            match_num   = ps.identifier
            phase_group = ps.phase_group

            provider_status = _PROVIDER_STATE_TO_LOCAL.get(ps.state)

            if sid in local_matches:
                local_status = local_matches[sid]
                cmds = await _update_existing_match(
                    db, sid, ps, local_status, provider_status, planned, station_by_stream, discord_by_startgg,
                    p1_name, p2_name, p1_avatar, p2_avatar, p1_eid, p2_eid, round_name, match_num, phase_group,
                    check_in_source=check_in_source, explicit_links=explicit_links, workspace_id=workspace_id,
                )
                if cmds:
                    pending_cmds.extend(cmds)
            else:
                await _insert_new_match(
                    db, sid, ps, tournament_slug, bot_manage_limit, planned, station_by_stream, discord_by_startgg,
                    p1_name, p2_name, p1_avatar, p2_avatar, p1_eid, p2_eid, round_name, match_num, phase_group,
                    explicit_links=explicit_links, workspace_id=workspace_id,
                )

        # Remove orphans — since provider.fetch_sets retrieves all paginated sets, orphan list is complete
        orphan_sids = [sid for sid in local_matches.keys() if sid not in found_sids]
        if orphan_sids:
            # Orphan-race guard (start.gg mode): the FINAL match of a phase completes,
            # the phase deactivates, fetch_sets stops returning it, and it lands here as
            # an orphan — possibly before the completion edge fired. If such an orphan was
            # still mid-flight and has a thread, archive it (with the thread id passed
            # explicitly, since we're about to delete the row).
            if check_in_source == 'startgg':
                for sid in orphan_sids:
                    if local_matches.get(sid) in ('called', 'in_progress'):
                        async with db.execute(
                            "SELECT discord_thread_id FROM active_matches WHERE set_id = ?" + (" AND workspace_id=?" if workspace_id is not None else ""), (sid,) + ((workspace_id,) if workspace_id is not None else ())
                        ) as c:
                            row = await c.fetchone()
                        thread_id = row[0] if row and row[0] else ""
                        if thread_id:
                            pending_cmds.append(f"startgg_finish {sid} {thread_id}")
            await db.executemany(
                "DELETE FROM active_matches WHERE set_id = ?" + (" AND workspace_id=?" if workspace_id is not None else ""),
                [(sid,) + ((workspace_id,) if workspace_id is not None else ()) for sid in orphan_sids]
            )

        await db.commit()

    # Enqueue Discord side-effect commands now the transaction is committed and the
    # write-lock released. add_hub_command nudges the bot to drain immediately.
    for cmd in pending_cmds:
        # Provider workers carry the durable tournament owner into the command
        # queue.  A command without this context could be consumed by another
        # tenant when set IDs overlap; legacy unowned fixtures retain the old
        # hook for compatibility.
        if workspace_id is not None:
            await add_hub_command(cmd, workspace_id=workspace_id)
        else:
            await add_hub_command(cmd)

async def delete_tournament_active_matches(slug: str, workspace_id: str | None = None):
    """Wipes local active matches for a tournament within the caller's workspace.

    The optional scope keeps legacy migration fixtures working, while every
    authenticated API caller supplies its trusted workspace so a colliding
    slug in another tenant cannot be reset accidentally.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        query = "DELETE FROM active_matches WHERE tournament_slug = ?"
        params: list[str] = [slug]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        await db.execute(query, params)
        await db.commit()

async def delete_active_match(set_id: str, workspace_id: str | None = None):
    """Deletes a single active match, never crossing a supplied workspace."""
    async with aiosqlite.connect(DB_PATH) as db:
        query, params = "DELETE FROM active_matches WHERE set_id = ?", [set_id]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        await db.execute(query, params)
        await db.commit()


async def update_active_match(match_id: str, *, workspace_id: str | None = None, **kwargs) -> bool:
    """Update one active match, scoped to a trusted workspace when supplied.

    The legacy no-workspace call is intentionally preserved for migration tools
    and existing unowned rows.  Authenticated API, bot, and worker paths must
    pass their resolved workspace, so knowing another tenant's provider set id
    cannot mutate its local projection.
    """
    if not kwargs:
        return False

    # Check if status is being updated and validate it
    if "status" in kwargs:
        new_status = kwargs["status"]
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                scope = " AND workspace_id = ?" if workspace_id is not None else ""
                params = (match_id,) + ((workspace_id,) if workspace_id is not None else ())
                async with db.execute("SELECT status FROM active_matches WHERE set_id = ?" + scope, params) as c:
                    row = await c.fetchone()
                    if row:
                        old_status = row["status"]
                        if old_status and old_status != new_status:
                            from backend.core.match_state import validate_transition
                            if not validate_transition(old_status, new_status):
                                await add_bot_feed(
                                    f"⚠️ Non-standard transition detected: {old_status} ➔ {new_status} for match {match_id}",
                                    "warn", workspace_id=workspace_id,
                                )
        except Exception as e:
            print(f"Error validating status transition: {e}")

    async with aiosqlite.connect(DB_PATH) as db:
        valid_cols = []
        async with db.execute("PRAGMA table_info(active_matches)") as cursor:
            info = await cursor.fetchall()
            valid_cols = [row[1] for row in info]

        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_cols}
        if not filtered_kwargs:
            return False

        keys = ", ".join([f"{k} = ?" for k in filtered_kwargs.keys()])
        # PostgreSQL boolean columns reject SQLite's legacy 0/1 integers.
        # Normalize at the repository boundary so bot workflow updates (for
        # example ``auto_dq_disarmed=0`` during Call) remain portable while
        # preserving the existing SQLite test/tool representation.
        values = [_database_value(key, value) for key, value in filtered_kwargs.items()]
        values.append(match_id)
        scope = ""
        if workspace_id is not None:
            scope = " AND workspace_id = ?"
            values.append(workspace_id)

        cursor = await db.execute(f"UPDATE active_matches SET {keys} WHERE set_id = ?{scope}", values)
        await db.commit()
        return cursor.rowcount == 1

async def get_player_override(entrant_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT * FROM player_overrides WHERE id = ?"
        params: list = [entrant_id]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as c:
            row = await c.fetchone()
            if row:
                return dict(zip([col[0] for col in c.description], row))
            return None

async def save_player_override(entrant_id: str, data: dict, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        # First, ensure the row exists
        await db.execute(
            "INSERT INTO player_overrides (id, workspace_id) VALUES (?, ?) ON CONFLICT (id) DO NOTHING",
            (entrant_id, workspace_id),
        )
        if workspace_id is not None:
            async with db.execute("SELECT workspace_id FROM player_overrides WHERE id = ?", (entrant_id,)) as c:
                owner = await c.fetchone()
            if owner and owner[0] not in (None, workspace_id):
                raise PermissionError("Player override belongs to another workspace")
            await db.execute(
                "UPDATE player_overrides SET workspace_id = ? WHERE id = ? AND workspace_id IS NULL",
                (workspace_id, entrant_id),
            )
        # Build the update query dynamically
        fields = []
        params = []
        mapping = {
            "name": "display_name",
            "team": "team",
            "country": "country",
            "cfn": "cfn",
            "avatar_url": "avatar_url"
        }
        for key, col in mapping.items():
            if key in data and data[key] is not None:
                fields.append(f"{col} = ?")
                params.append(data[key])
        
        if fields:
            params.append(entrant_id)
            query = f"UPDATE player_overrides SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            if workspace_id is not None:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            await db.execute(query, params)
        await db.commit()

async def get_all_player_overrides(workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT * FROM player_overrides"
        params: list = []
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as c:
            rows = await c.fetchall()
            out = {}
            for row in rows:
                d = dict(zip([col[0] for col in c.description], row))
                # Map database column names back to frontend property names
                out[d.get('id', '')] = {
                    "name": d.get('display_name'),
                    "team": d.get('team'),
                    "country": d.get('country'),
                    "cfn": d.get('cfn'),
                    "avatar_url": d.get('avatar_url')
                }
            return out

async def delete_player_override(entrant_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query = "DELETE FROM player_overrides WHERE id = ?"
        params: list = [entrant_id]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        await db.execute(query, params)
        await db.commit()

async def delete_all_player_overrides(workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if workspace_id is None:
            await db.execute("DELETE FROM player_overrides")
        else:
            await db.execute("DELETE FROM player_overrides WHERE workspace_id = ?", (workspace_id,))
        await db.commit()

# ── Connections ────────────────────────────────────────────────────────────
async def get_connection(key: str, default: str = None) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM connections WHERE key = ?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else default

async def set_connection(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO connections (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (key, value))
        await db.commit()


async def delete_connections(keys: list[str]) -> None:
    """Remove a small, explicit group of connection values."""
    if not keys:
        return
    placeholders = ", ".join("?" for _ in keys)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"DELETE FROM connections WHERE key IN ({placeholders})", keys)
        await db.commit()


async def create_oauth_state(provider: str, state: str, ttl_seconds: int, account_id: str | None = None) -> None:
    """Store one anti-CSRF state for a provider OAuth redirect."""
    expires_at = int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + ttl_seconds
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (int(datetime.datetime.now(datetime.timezone.utc).timestamp()),))
        await db.execute(
            "INSERT INTO oauth_states (provider, state, account_id, expires_at) VALUES (?, ?, ?, ?)",
            (provider, state, account_id, expires_at),
        )
        await db.commit()


async def consume_oauth_state(provider: str, state: str) -> str | None:
    """Atomically consume a non-expired OAuth state so callback links cannot replay."""
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT account_id FROM oauth_states WHERE provider = ? AND state = ? AND expires_at > ?",
            (provider, state, now),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            await db.execute("DELETE FROM oauth_states WHERE provider = ? AND state = ?", (provider, state))
        await db.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (now,))
        await db.commit()
        return str(row[0]) if row and row[0] else None

async def get_all_connections() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM connections") as c:
            rows = await c.fetchall()
            return {r[0]: r[1] for r in rows}

async def get_setting(key: str, default: str = None) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM global_settings WHERE key = ?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO global_settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (key, value))
        await db.commit()

async def get_all_settings() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM global_settings") as c:
            rows = await c.fetchall()
            return {r[0]: r[1] for r in rows}

async def clear_settings_prefix(prefix: str):
    """Delete every global_settings row whose key starts with `prefix`.

    Used to reset the per-event one-shot dispatcher stop flags
    (`_dispatcher_stop_signaled_{slug}_{event_id}`) in one shot, without having
    to enumerate every event id."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM global_settings WHERE key LIKE ? ESCAPE '\\'",
            (prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",)
        )
        await db.commit()


# ── Conflicts ──────────────────────────────────────────────────────────────
async def add_conflict(set_id: str, p1_claim: str, p2_claim: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conflicts (set_id, p1_claim, p2_claim) VALUES (?, ?, ?)",
            (set_id, p1_claim, p2_claim)
        )
        await db.commit()

async def get_conflicts(resolved: bool = False, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT c.* FROM conflicts c"
        params: list = [resolved]
        if workspace_id is not None:
            query += " JOIN active_matches am ON am.set_id = c.set_id WHERE am.workspace_id = ? AND c.resolved = ?"
            params = [workspace_id, resolved]
        else:
            query += " WHERE c.resolved = ?"
        query += " ORDER BY c.created_at DESC"
        async with db.execute(query, params
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def get_conflict(conflict_id: int, workspace_id: str | None = None):
    """Fetch a single conflict row (incl. its set_id) for score-based resolution."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT c.* FROM conflicts c"
        params: list = [conflict_id]
        if workspace_id is not None:
            query += " JOIN active_matches am ON am.set_id = c.set_id WHERE c.id = ? AND am.workspace_id = ?"
            params.append(workspace_id)
        else:
            query += " WHERE c.id = ?"
        async with db.execute(query, params
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_conflict_by_set_id(set_id: str, resolved: bool = False):
    """Most recent (un)resolved conflict for a set — used by the Discord investigation."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conflicts WHERE set_id = ? AND resolved = ? ORDER BY id DESC LIMIT 1",
            (str(set_id), resolved),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def update_conflict_claim(conflict_id: int, slot: str, text: str):
    """Store a player's investigation statement (slot is 'p1' or 'p2')."""
    col = "p1_claim" if slot == "p1" else "p2_claim"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE conflicts SET {col} = ? WHERE id = ?", (text, conflict_id)
        )
        await db.commit()

async def update_conflict_summary(conflict_id: int, summary: str):
    """Store the AI-generated one-line dispute summary."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conflicts SET ai_summary = ? WHERE id = ?", (summary, conflict_id)
        )
        await db.commit()

async def resolve_conflict(conflict_id: int, resolution: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if workspace_id is None:
            await db.execute(
                "UPDATE conflicts SET resolved = TRUE, resolution = ? WHERE id = ?",
                (resolution, conflict_id)
            )
        else:
            await db.execute(
                """UPDATE conflicts
                   SET resolved = TRUE, resolution = ?
                 WHERE id = ?
                   AND EXISTS (
                       SELECT 1 FROM active_matches am
                        WHERE am.set_id = conflicts.set_id
                          AND am.workspace_id = ?
                   )""",
                (resolution, conflict_id, workspace_id)
            )
        await db.commit()

# ── Bot Feed ───────────────────────────────────────────────────────────────
async def add_bot_feed(message: str, level: str = "info", workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_feed (message, level, workspace_id) VALUES (?, ?, ?)",
            (message, level, workspace_id)
        )
        # Keep the last 200 entries per workspace; one tenant cannot evict
        # another tenant's operational history.
        if workspace_id is None:
            await db.execute('''
                DELETE FROM bot_feed WHERE id NOT IN (
                    SELECT id FROM bot_feed WHERE workspace_id IS NULL ORDER BY id DESC LIMIT 200
                ) AND workspace_id IS NULL
            ''')
        else:
            await db.execute('''
                DELETE FROM bot_feed WHERE workspace_id = ? AND id NOT IN (
                    SELECT id FROM bot_feed WHERE workspace_id = ? ORDER BY id DESC LIMIT 200
                )
            ''', (workspace_id, workspace_id))
        await db.commit()

async def get_bot_feed(limit: int = 50, offset: int = 0, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM bot_feed"
        params: list = []
        if workspace_id is None:
            query += " WHERE workspace_id IS NULL"
        else:
            query += " WHERE workspace_id = ?"
            params.append(workspace_id)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend((limit, offset))
        async with db.execute(
            query, params
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def clear_bot_feed(workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if workspace_id is None:
            await db.execute("DELETE FROM bot_feed WHERE workspace_id IS NULL")
        else:
            await db.execute("DELETE FROM bot_feed WHERE workspace_id = ?", (workspace_id,))
        await db.commit()

# ── Hub Commands ───────────────────────────────────────────────────────────
# Event-driven outbox: the hub_commands table is the durable queue, but instead
# of polling it, each process registers a listener that is fired the instant a
# command is enqueued so the consumer (the bot) can drain immediately. The API
# process registers a listener that nudges the bot over its WebSocket; the bot
# process registers one that triggers its own in-process drain.
_hub_command_listener = None

def set_hub_command_listener(callback):
    """Register a zero-arg callback fired (best-effort) right after a hub command
    is committed. Used to drain the queue event-driven instead of by polling."""
    global _hub_command_listener
    _hub_command_listener = callback

def _fire_hub_command_listener():
    cb = _hub_command_listener
    if cb is None:
        return
    try:
        cb()
    except Exception as e:
        print(f"[DB] hub command listener error: {e}")

async def add_hub_command(command_text: str, *, source: str = "manual", workspace_id: str | None = None):
    """Enqueue one Hub command with a non-forgeable operational source.

    ``source`` is intentionally separate from command text so the dispatcher
    kill switch can cancel only pending automatic work, never a TO command.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO hub_commands (command_text, source, status, workspace_id) VALUES (?, ?, 'pending', ?)",
            (command_text, source, workspace_id)
        )
        await db.commit()
    # Fire AFTER commit so the consumer sees the row when it drains.
    _fire_hub_command_listener()

async def get_pending_hub_commands(workspace_id: str | None = None):
    """Return pending Hub commands for a trusted worker workspace.

    The unscoped form is retained for migration/tests and deliberately should
    not be used by a multi-tenant worker.  Runtime consumers pass the
    workspace selected by their integration account or task context.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        scope = " AND workspace_id = ?" if workspace_id is not None else ""
        params = (workspace_id,) if workspace_id is not None else ()
        async with db.execute(
            "SELECT * FROM hub_commands WHERE status = 'pending'" + scope + " ORDER BY created_at ASC",
            params,
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def claim_pending_hub_commands(
    lease_owner: str, *, limit: int = 25, lease_seconds: int = 120,
    workspace_id: str | None = None,
) -> list[dict]:
    """Atomically claim queue rows across API/bot processes.

    A worker workspace is an authorization boundary, not merely a display
    filter.  When supplied, both the claim and returned rows are constrained
    to it, so a bot processing one integration account cannot drain another
    workspace's queue.  The unscoped form remains only for legacy migration
    fixtures and single-tenant compatibility during the staged rollout.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        scope = " AND workspace_id = ?" if workspace_id is not None else ""
        scope_params = (workspace_id,) if workspace_id is not None else ()
        if is_postgres():
            rows = await (await db.execute(
                """WITH candidates AS (
                     SELECT id FROM hub_commands
                     WHERE (status='pending' OR (status='processing' AND lease_expires_at<CURRENT_TIMESTAMP))""" + scope + """
                     ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT ?
                   )
                   UPDATE hub_commands h SET status='processing', lease_owner=?,
                     lease_expires_at=CURRENT_TIMESTAMP + (? * INTERVAL '1 second'),
                     attempts=COALESCE(attempts,0)+1
                   FROM candidates c WHERE h.id=c.id RETURNING h.*""",
                (*scope_params, limit, lease_owner, lease_seconds),
            )).fetchall()
        else:
            ids = await (await db.execute(
                """SELECT id FROM hub_commands
                   WHERE (status='pending' OR (status='processing' AND lease_expires_at<CURRENT_TIMESTAMP))""" + scope + """
                   ORDER BY created_at LIMIT ?""", (*scope_params, limit)
            )).fetchall()
            if not ids:
                await db.commit(); return []
            placeholders = ",".join("?" for _ in ids)
            id_values = [row[0] for row in ids]
            await db.execute(
                f"""UPDATE hub_commands SET status='processing', lease_owner=?,
                    lease_expires_at=datetime(CURRENT_TIMESTAMP, '+' || ? || ' seconds'),
                    attempts=COALESCE(attempts,0)+1 WHERE id IN ({placeholders})""",
                (lease_owner, lease_seconds, *id_values),
            )
            rows = await (await db.execute(
                f"SELECT * FROM hub_commands WHERE id IN ({placeholders}) ORDER BY created_at", id_values
            )).fetchall()
        await db.commit()
        return [dict(row) for row in rows]


async def finish_hub_command(command_id: int, lease_owner: str, status: str, error: str | None = None) -> bool:
    if status not in {"done", "error", "cancelled", "needs_review"}:
        raise ValueError("Invalid terminal command state")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """UPDATE hub_commands SET status=?, last_error=?, lease_owner=NULL, lease_expires_at=NULL
               WHERE id=? AND status='processing' AND lease_owner=?""",
            (status, error, command_id, lease_owner),
        )
        await db.commit()
        return cursor.rowcount == 1
async def purge_incomplete_registrations(tournament_slug: str):
    """
    Deletes players who haven't completed registration after the deadline.
    For simplicity, this deletes all is_verified=FALSE players.
    In a real scenario, you'd filter by tournament participation too.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM players WHERE is_verified = FALSE")
        await db.commit()

async def update_hub_command_status(command_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE hub_commands SET status = ? WHERE id = ?",
            (status, command_id)
        )
        await db.commit()


# ── Auto-Dispatcher Queries ──────────────────────────────────────────────
def resolve_dispatch_budget(row: dict) -> tuple[int, int]:
    """Return (concurrency, stop_at) for a tournament row, honoring an explicit 0.

    A TO can legitimately set stop_at=0 ("auto-dispatch all the way to the final").
    The old `int(value or 8)` form treated that 0 as falsy and silently restored
    the default 8 — so only a genuinely missing (None) value falls back here.
    """
    conc = row.get("auto_dispatch_concurrency")
    stop = row.get("auto_dispatch_stop_at")
    concurrency = max(1, int(conc if conc is not None else 1))
    stop_at = max(0, int(stop if stop is not None else 8))
    return concurrency, stop_at


async def get_dispatch_eligible_tournaments(workspace_id: str | None = None) -> list[dict]:
    """Tournaments with the auto-dispatcher armed."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = ("SELECT slug, name, auto_dispatch_concurrency, auto_dispatch_stop_at, workspace_id "
                 "FROM tournaments WHERE auto_dispatch_enabled = TRUE")
        params: list = []
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_dispatch_eligible_events(workspace_id: str | None = None) -> list[dict]:
    """Each (tournament, event) pair with the auto-dispatcher armed.

    Option A — per-event budget: every event under an armed tournament becomes
    its own independent dispatch queue, so a multi-game tournament (e.g. SF6 +
    Tekken 8) never shares concurrency or Top-N thresholds across games.
    Legacy/single-event rows surface as one bucket with event_id=''.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT t.slug, t.name, t.workspace_id,
                   t.auto_dispatch_concurrency, t.auto_dispatch_stop_at,
                   COALESCE(am.event_id, '')   AS event_id,
                   COALESCE(am.event_name, '') AS event_name
            FROM tournaments t
            JOIN active_matches am ON am.tournament_slug = t.slug
              AND (t.workspace_id IS NULL OR am.workspace_id = t.workspace_id)
            WHERE t.auto_dispatch_enabled = TRUE
            """ + (" AND t.workspace_id = ?" if workspace_id is not None else "") + """
            GROUP BY t.slug, t.name, t.workspace_id,
                     t.auto_dispatch_concurrency, t.auto_dispatch_stop_at,
                     COALESCE(am.event_id, ''), COALESCE(am.event_name, '')
            """
        async with db.execute(query, ([workspace_id] if workspace_id is not None else [])) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def count_active_dispatched(tournament_slug: str, event_id: str | None = None, workspace_id: str | None = None) -> int:
    """Currently-occupying-time matches the dispatcher has on the wire.
    Counts called + in_progress matches that are bot-managed for the tournament.
    When event_id is given, the count is scoped to that event (Option A budget);
    pass '' to match legacy/untagged rows."""
    sql = ("SELECT COUNT(*) FROM active_matches "
           "WHERE tournament_slug = ? AND bot_enabled = TRUE "
           "AND status IN ('called', 'in_progress')")
    params: list = [tournament_slug]
    if workspace_id is not None:
        sql += " AND workspace_id = ?"
        params.append(workspace_id)
    if event_id is not None:
        sql += " AND COALESCE(event_id, '') = ?"
        params.append(event_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(sql, params) as cursor:
            row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def count_remaining_event_matches(tournament_slug: str, event_id: str | None = None, workspace_id: str | None = None) -> int:
    """Total uncompleted matches the dispatcher knows about for the tournament.
    Includes TBD/unresolved sets so a Top-8 threshold isn't tripped prematurely
    by pool matches still being resolved. When event_id is given, the Top-N
    threshold is evaluated per event; pass '' to match legacy/untagged rows."""
    sql = ("SELECT COUNT(*) FROM active_matches "
           "WHERE tournament_slug = ? AND status NOT IN ('complete', 'dq')")
    params: list = [tournament_slug]
    if workspace_id is not None:
        sql += " AND workspace_id = ?"
        params.append(workspace_id)
    if event_id is not None:
        sql += " AND COALESCE(event_id, '') = ?"
        params.append(event_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(sql, params) as cursor:
            row = await cursor.fetchone()
    return int(row[0] if row else 0)


async def get_dispatch_candidates(tournament_slug: str, limit: int, event_id: str | None = None, workspace_id: str | None = None) -> list[dict]:
    """Find the next bot-managed matches that are safe to auto-call.

    Excludes:
      - matches with TBD/missing entrants (upstream bracket unresolved)
      - anything already called or in progress (those are counted toward concurrency)

    Stream-flagged matches are deliberately INCLUDED: the auto-dispatcher moves
    them not_started → called like any other match (workflows.json), and the
    stream station is bound later, at the called → in_progress transition (the
    `on_stream` overlay). Preview/unready featured picks are still excluded by
    the entrant/TBD guards above.

    When event_id is given, candidates are scoped to that event so a multi-game
    tournament never cross-routes (pass '' to match legacy/untagged rows).
    Orders by phase_group then match_number for predictable pool progression.
    """
    sql = """
        SELECT * FROM active_matches
        WHERE tournament_slug = ?
          AND status = 'not_started'
          AND bot_enabled = TRUE
          AND p1_entrant_id IS NOT NULL AND p1_entrant_id != ''
          AND p2_entrant_id IS NOT NULL AND p2_entrant_id != ''
          AND p1_name IS NOT NULL AND p1_name != '' AND p1_name != 'TBD'
          AND p2_name IS NOT NULL AND p2_name != '' AND p2_name != 'TBD'
    """
    params: list = [tournament_slug]
    if workspace_id is not None:
        sql = sql.replace("WHERE tournament_slug = ?", "WHERE tournament_slug = ? AND workspace_id = ?")
        params.append(workspace_id)
    if event_id is not None:
        sql += " AND COALESCE(event_id, '') = ?"
        params.append(event_id)
    match_order = (
        "CASE WHEN match_number ~ '^[0-9]+$' THEN match_number::BIGINT ELSE 999999 END"
        if is_postgres() else
        "CASE WHEN match_number GLOB '[0-9]*' AND match_number NOT GLOB '*[^0-9]*' "
        "THEN CAST(match_number AS INTEGER) ELSE 999999 END"
    )
    sql += f"""
        ORDER BY
          COALESCE(NULLIF(phase_group, ''), 'zzzz'),
          {match_order},
          created_at
        LIMIT ?
    """
    params.append(int(limit))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_available_stream_station(event_id: str | None, workspace_id: str | None = None) -> dict | None:
    """An idle stream station bound to this event, or None.

    Used by the green-room dispatch: a stream-flagged match may only be routed
    to a station with is_stream_station=1 AND a matching event_id that isn't
    already hosting a called/in_progress match. Pass '' to match stations left
    unbound to any event.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT s.* FROM stations s
            WHERE s.is_stream_station = TRUE
              AND COALESCE(s.event_id, '') = ?
              AND COALESCE(s.hidden, FALSE) = FALSE
            AND s.id NOT IN (
                SELECT station_id FROM active_matches
                WHERE station_id IS NOT NULL
                  AND status IN ('called', 'in_progress')
                  AND (workspace_id = s.workspace_id OR (workspace_id IS NULL AND s.workspace_id IS NULL))
            )
            ORDER BY s.id
            LIMIT 1
            """
        params: list = [event_id or ""]
        if workspace_id is not None:
            query = query.replace("WHERE s.is_stream_station", "WHERE s.workspace_id = ? AND s.is_stream_station")
            params.insert(0, workspace_id)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

def should_bot_manage_match(round_name: str, phase_group: str, limit_setting: str) -> bool:
    limit_lower = (limit_setting or "").lower()

    if not limit_lower or limit_lower == "off":
        return False
    if limit_lower == "all" or limit_lower == "on":
        return True
        
    round_lower = (round_name or "").lower()
    phase_lower = (phase_group or "").lower()
    
    if limit_lower == "top8":
        is_top8 = "top 8" in phase_lower or "top8" in phase_lower or "final" in round_lower or "semi" in round_lower or "quarter" in round_lower
        return not is_top8
        
    if limit_lower == "top16":
        is_top16 = "top 16" in phase_lower or "top16" in phase_lower or "top 8" in phase_lower or "top8" in phase_lower or "final" in round_lower or "semi" in round_lower or "quarter" in round_lower
        return not is_top16
        
    if limit_lower in phase_lower:
        return True
        
    return True

async def get_player_in_progress_match(discord_id: str, workspace_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM active_matches WHERE status = 'in_progress' AND (p1_discord = ? OR p2_discord = ?)"
        params: list = [discord_id, discord_id]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ── Provider V2 dark foundation repositories ───────────────────────────────
# These functions are intentionally not invoked by the legacy runtime in Phase 2.
# They provide durable storage for later feature-flagged services only.


async def create_provider_command_v2(command: dict) -> dict:
    """Insert one remote-provider command or return its existing idempotent record."""
    required = {
        "id", "tournament_slug", "set_id", "provider_type", "provider_account_id",
        "action", "idempotency_key", "payload_digest",
    }
    missing = required - command.keys()
    if missing:
        raise ValueError(f"Missing provider command fields: {', '.join(sorted(missing))}")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO provider_command_ledger (
                id, workspace_id, tournament_slug, set_id, provider_type, provider_account_id,
                action, state, idempotency_key, payload_digest, expected_result_json,
                precondition_revision, lease_until, next_retry_at, attempt_count,
                error_message, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_type, provider_account_id, idempotency_key) DO NOTHING
            """,
            (
                command["id"], command.get("workspace_id"), command["tournament_slug"], command["set_id"],
                command["provider_type"], command["provider_account_id"], command["action"],
                command.get("state", "pending"), command["idempotency_key"],
                command["payload_digest"], json.dumps(command.get("expected_result", {})),
                command.get("precondition_revision"), command.get("lease_until"),
                command.get("next_retry_at"), int(command.get("attempt_count", 0)),
                command.get("error_message"), command.get("reason"),
            ),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM provider_command_ledger WHERE provider_type = ? "
            "AND provider_account_id = ? AND idempotency_key = ?",
            (command["provider_type"], command["provider_account_id"], command["idempotency_key"]),
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else {}


async def record_dispatcher_decision(
    *, decision_key: str, tournament_slug: str, event_id: str, set_id: str | None,
    decision: str, reason_code: str, explanation: str, workspace_id: str | None = None,
) -> None:
    """Store one deterministic dispatch decision without per-tick log spam."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO dispatcher_decisions (
                   decision_key, workspace_id, tournament_slug, event_id, set_id, decision,
                   reason_code, explanation
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(decision_key) DO UPDATE SET
                   last_seen_at=CURRENT_TIMESTAMP,
                   seen_count=dispatcher_decisions.seen_count + 1""",
            (decision_key, workspace_id, tournament_slug, event_id or "", set_id, decision, reason_code, explanation),
        )
        await db.commit()


async def claim_dispatcher_match(set_id: str, tournament_slug: str, workspace_id: str | None = None) -> bool:
    """Atomically claim a selected match while the dispatcher master is on.

    A stale claim can be reclaimed after two minutes. A queued/cancelled claim
    is never overwritten: the match lifecycle remains the source of truth.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            "SELECT value FROM global_settings WHERE key='auto_dispatch_master_switch'"
        ) as cursor:
            setting = await cursor.fetchone()
        if not setting or str(setting[0]).lower() != "on":
            await db.rollback()
            return False
        stale_claim_clause = "CURRENT_TIMESTAMP - INTERVAL '2 minutes'" if is_postgres() else "datetime('now', '-2 minutes')"
        cursor = await db.execute(
            f"""INSERT INTO dispatcher_dispatch_claims (set_id, workspace_id, tournament_slug, state)
               VALUES (?, ?, ?, 'claimed')
               ON CONFLICT(set_id) DO UPDATE SET
                   workspace_id=excluded.workspace_id,
                   tournament_slug=excluded.tournament_slug,
                   state='claimed',
                   claimed_at=CURRENT_TIMESTAMP,
                   updated_at=CURRENT_TIMESTAMP
               WHERE (dispatcher_dispatch_claims.workspace_id IS NULL
                      OR excluded.workspace_id IS NULL
                      OR dispatcher_dispatch_claims.workspace_id=excluded.workspace_id)
                 AND dispatcher_dispatch_claims.state='claimed'
                 AND dispatcher_dispatch_claims.claimed_at < {stale_claim_clause}""",
            (set_id, workspace_id, tournament_slug),
        )
        claimed = cursor.rowcount == 1
        if claimed:
            await db.commit()
        else:
            await db.rollback()
    return claimed


async def dispatcher_claim_is_active(set_id: str, workspace_id: str | None = None) -> bool:
    """Check the global and tournament switches immediately before local Call.

    This second check closes the gap between policy selection and Hub workflow
    entry: disabling one tournament cancels only its automatic work, while a
    manual Call remains unrelated.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT 1
               FROM dispatcher_dispatch_claims c
               JOIN tournaments t ON t.slug=c.tournament_slug
               JOIN global_settings s ON s.key='auto_dispatch_master_switch'
               WHERE c.set_id=? AND c.state='claimed'
                 AND (CAST(? AS TEXT) IS NULL OR c.workspace_id=CAST(? AS TEXT) )
                 AND (CAST(? AS TEXT) IS NULL OR t.workspace_id=CAST(? AS TEXT) )
                 AND lower(s.value)='on'
                 AND COALESCE(t.auto_dispatch_enabled, FALSE)=TRUE""",
            (set_id, workspace_id, workspace_id, workspace_id, workspace_id),
        ) as cursor:
            return await cursor.fetchone() is not None


async def mark_dispatcher_claim_queued(set_id: str, workspace_id: str | None = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE dispatcher_dispatch_claims SET state='queued', updated_at=CURRENT_TIMESTAMP "
            "WHERE set_id=? AND state='claimed'" + (" AND workspace_id=?" if workspace_id is not None else ""),
            (set_id,) + ((workspace_id,) if workspace_id is not None else ()),
        )
        await db.commit()


async def release_dispatcher_claim(set_id: str, workspace_id: str | None = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        query = "DELETE FROM dispatcher_dispatch_claims WHERE set_id=? AND state='claimed'"
        params: list = [set_id]
        if workspace_id is not None:
            query += " AND workspace_id=?"
            params.append(workspace_id)
        await db.execute(query, params)
        await db.commit()


async def cancel_pending_dispatcher_work(tournament_slug: str | None = None) -> int:
    """Cancel automatic work that has not begun; manual commands are untouched.

    Supplying a tournament scope is the normal per-tournament pause path.  The
    global Kill Switch intentionally omits it and cancels every dispatcher item.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        if tournament_slug is None:
            commands = await db.execute(
                "UPDATE hub_commands SET status='cancelled' WHERE source='dispatcher' AND status='pending'"
            )
            claims = await db.execute(
                "UPDATE dispatcher_dispatch_claims SET state='cancelled', updated_at=CURRENT_TIMESTAMP "
                "WHERE state IN ('claimed', 'queued')"
            )
        else:
            commands = await db.execute(
                """UPDATE hub_commands SET status='cancelled'
                   WHERE source='dispatcher' AND status='pending'
                     AND EXISTS (
                       SELECT 1 FROM dispatcher_dispatch_claims c
                       WHERE c.tournament_slug=?
                         AND hub_commands.command_text='call_match ' || c.set_id
                     )""",
                (tournament_slug,),
            )
            claims = await db.execute(
                """UPDATE dispatcher_dispatch_claims
                   SET state='cancelled', updated_at=CURRENT_TIMESTAMP
                   WHERE tournament_slug=? AND state IN ('claimed', 'queued')""",
                (tournament_slug,),
            )
        await db.commit()
    return max(0, commands.rowcount) + max(0, claims.rowcount)


async def get_provider_command_v2(command_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM provider_command_ledger WHERE id = ?", (command_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def get_open_provider_command_for_match_v2(match_id: str, action: str, workspace_id: str | None = None) -> dict | None:
    """Return the one unresolved remote command for a match/action, if any.

    A score mutation is not safe to parallelize: a second payload can advance a
    bracket differently while the first request outcome is still unknown.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        scope = " AND workspace_id = ?" if workspace_id is not None else ""
        params = (match_id, action) + ((workspace_id,) if workspace_id is not None else ())
        async with db.execute(
            """SELECT * FROM provider_command_ledger
               WHERE set_id=? AND action=?""" + scope + """
                 AND state IN ('pending', 'sending', 'acknowledged', 'retryable')
               ORDER BY created_at DESC LIMIT 1""",
            params,
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def set_match_sync_status_v2(
    match_id: str, sync_status: str, *, reason: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    """Persist remote-command certainty without claiming a Hub completion."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        scope = " AND workspace_id=?" if workspace_id is not None else ""
        params = (sync_status, reason, match_id) + ((workspace_id,) if workspace_id is not None else ())
        await db.execute(
            """UPDATE active_matches SET sync_status=?, sync_reason=? WHERE set_id=?""" + scope,
            params,
        )
        async with db.execute("SELECT * FROM active_matches WHERE set_id=?" + scope,
                              (match_id,) + ((workspace_id,) if workspace_id is not None else ())) as cursor:
            row = await cursor.fetchone()
        await db.commit()
    if not row:
        raise ValueError(f"Unknown match: {match_id}")
    return dict(row)


async def record_targeted_snapshot_observation_v2(
    match_id: str,
    *,
    observed_at: str | None,
    revision: str | None,
    provider_state_raw: str | None = None,
    provider_state: ProviderSetState | None = None,
) -> None:
    """Record one included set from a narrow snapshot without completing it.

    A narrow preflight or result-verification snapshot cannot establish that
    *other* bracket records disappeared, but it is authoritative for the set
    which it actually contains.  Preserve its provider projection separately
    from Hub workflow state.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT provider_revision FROM active_matches WHERE set_id=?", (match_id,)
        ) as cursor:
            existing = await cursor.fetchone()
        if not existing:
            return
        if _revision_is_older(revision, existing["provider_revision"]):
            return
        normalized = provider_state.name.lower() if provider_state is not None else None
        await db.execute(
            """UPDATE active_matches
               SET last_successful_snapshot_at=COALESCE(?, CURRENT_TIMESTAMP),
                   provider_revision=COALESCE(?, provider_revision),
                   provider_state_raw=COALESCE(?, provider_state_raw),
                   provider_state_normalized=COALESCE(?, provider_state_normalized),
                   provider_observed_at=COALESCE(?, provider_observed_at)
               WHERE set_id=?""",
            (observed_at, revision, provider_state_raw, normalized, observed_at, match_id),
        )
        await db.commit()


async def update_provider_command_state_v2(command_id: str, state: str, *, reason: str | None = None) -> dict:
    """Persist one ledger-state transition; no remote mutation is performed here."""
    allowed = {
        "pending", "sending", "acknowledged", "snapshot_verified", "retryable",
        "permanent_failure", "conflict", "needs_review",
    }
    if state not in allowed:
        raise ValueError(f"Unsupported provider command state: {state}")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """UPDATE provider_command_ledger
               SET state=?, reason=COALESCE(?, reason), lease_owner=NULL, lease_until=NULL,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (state, reason, command_id),
        )
        async with db.execute("SELECT * FROM provider_command_ledger WHERE id=?", (command_id,)) as cursor:
            row = await cursor.fetchone()
        await db.commit()
    if not row:
        raise ValueError(f"Unknown provider command: {command_id}")
    return dict(row)


async def claim_due_provider_commands_v2(
    now: str, lease_until: str, *, limit: int = 20, lease_owner: str = "legacy",
    workspace_id: str | None = None,
) -> list[dict]:
    """Lease due remote commands without executing them.

    A later worker will call this under a feature flag. Phase 2 only exposes the
    crash-recovery primitive for tests; no startup path invokes it.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        # PostgreSQL must lock the candidate rows, not merely replace SQLite's
        # BEGIN IMMEDIATE with BEGIN. SKIP LOCKED lets another worker continue
        # with unrelated work instead of racing the same command.
        claim_lock = " FOR UPDATE SKIP LOCKED" if is_postgres() else ""
        workspace_scope = " AND workspace_id = ?" if workspace_id is not None else ""
        async with db.execute(
            """
            SELECT id FROM provider_command_ledger
            WHERE ((
                state IN ('pending', 'retryable')
                AND (next_retry_at IS NULL OR next_retry_at <= ?)
            ) OR (
                state = 'sending' AND lease_until IS NOT NULL AND lease_until <= ?
            ))
            """ + workspace_scope + """
            ORDER BY created_at
            LIMIT ?
            """ + claim_lock,
            (now, now, *((workspace_id,) if workspace_id is not None else ()), int(limit)),
        ) as cursor:
            command_ids = [str(row[0]) for row in await cursor.fetchall()]
        if command_ids:
            placeholders = ", ".join("?" for _ in command_ids)
            await db.execute(
                f"UPDATE provider_command_ledger SET state = 'sending', lease_owner = ?, lease_until = ?, "
                f"attempt_count = attempt_count + 1, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id IN ({placeholders})" + workspace_scope,
                [lease_owner, lease_until, *command_ids, *((workspace_id,) if workspace_id is not None else ())],
            )
        rows: list[dict] = []
        if command_ids:
            placeholders = ", ".join("?" for _ in command_ids)
            async with db.execute(
                f"SELECT * FROM provider_command_ledger WHERE id IN ({placeholders})" + workspace_scope,
                [*command_ids, *((workspace_id,) if workspace_id is not None else ())],
            ) as cursor:
                rows = [dict(row) for row in await cursor.fetchall()]
        await db.commit()
    return rows


async def renew_provider_command_lease_v2(command_id: str, lease_owner: str, lease_until: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """UPDATE provider_command_ledger SET lease_until=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND state='sending' AND lease_owner=?""",
            (lease_until, command_id, lease_owner),
        )
        await db.commit()
    return cursor.rowcount == 1


async def enqueue_workflow_outbox_v2(event: dict) -> dict:
    """Persist an external Hub side effect without dispatching it."""
    required = {"event_id", "match_id", "event_type", "deduplication_key"}
    missing = required - event.keys()
    if missing:
        raise ValueError(f"Missing workflow outbox fields: {', '.join(sorted(missing))}")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        outbox_insert = await db.execute(
            """
            INSERT INTO workflow_outbox (
                event_id, match_id, event_type, payload_json, deduplication_key,
                status, attempts, next_attempt_at, workspace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deduplication_key) DO NOTHING
            """,
            (
                event["event_id"], event["match_id"], event["event_type"],
                json.dumps(event.get("payload", {})), event["deduplication_key"],
                event.get("status", "pending"), int(event.get("attempts", 0)),
                event.get("next_attempt_at"), event.get("workspace_id"),
            ),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM workflow_outbox WHERE deduplication_key = ?",
            (event["deduplication_key"],),
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else {}


async def update_hub_workflow_and_enqueue_outbox_v2(
    match_id: str, hub_status: str, event: dict, *, workspace_id: str | None = None
) -> dict:
    """Atomically write V2 Hub state and its later local side effect.

    This deliberately leaves legacy ``active_matches.status`` untouched.  No Phase-2
    runtime calls this function; later workflow adoption must use it as one database
    transaction so a persisted Call cannot lose its Discord/OBS outbox event.
    """
    required = {"event_id", "event_type", "deduplication_key"}
    missing = required - event.keys()
    if missing:
        raise ValueError(f"Missing workflow outbox fields: {', '.join(sorted(missing))}")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        match_scope = " AND workspace_id = ?" if workspace_id is not None else ""
        update = await db.execute(
            "UPDATE active_matches SET hub_status = ? WHERE set_id = ?" + match_scope,
            (hub_status, match_id, *((workspace_id,) if workspace_id is not None else ())),
        )
        if update.rowcount != 1:
            await db.rollback()
            raise ValueError(f"Unknown match: {match_id}")
        # Hub state, audit trail, and side-effect outbox are committed together.
        # The audit row is deliberately best-effort for legacy unowned rows;
        # owned Workspace matches always carry the durable scope.
        match_row = await (await db.execute(
            "SELECT workspace_id, tournament_slug FROM active_matches WHERE set_id = ?" + match_scope,
            (match_id, *((workspace_id,) if workspace_id is not None else ())),
        )).fetchone()
        outbox_insert = await db.execute(
            """
            INSERT INTO workflow_outbox (
                event_id, match_id, event_type, payload_json, deduplication_key,
                status, attempts, next_attempt_at, workspace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deduplication_key) DO NOTHING
            """,
            (
                event["event_id"], match_id, event["event_type"],
                json.dumps(event.get("payload", {})), event["deduplication_key"],
                event.get("status", "pending"), int(event.get("attempts", 0)),
                event.get("next_attempt_at"),
                str(match_row[0]) if match_row else workspace_id,
            ),
        )
        if outbox_insert.rowcount == 1 and match_row and match_row[0]:
            await db.execute(
                """INSERT INTO audit_events
                   (id, workspace_id, actor_id, action, target_type, target_id,
                    outcome, trace_id, detail_json)
                   VALUES (?, ?, ?, ?, 'match', ?, 'accepted', ?, ?)""",
                (
                    str(uuid.uuid4()), str(match_row[0]), event.get("actor_id"),
                    str(event.get("event_type") or "hub_workflow_transition"),
                    str(match_id), event.get("trace_id"),
                    json.dumps(_redact_audit(event.get("payload", {})), separators=(",", ":")),
                ),
            )
        async with db.execute(
            "SELECT * FROM workflow_outbox WHERE deduplication_key = ?",
            (event["deduplication_key"],),
        ) as cursor:
            row = await cursor.fetchone()
        await db.commit()
    return dict(row) if row else {}


async def claim_due_workflow_outbox_v2(
    now: str, lease_until: str, *, limit: int = 20, lease_owner: str = "legacy",
    workspace_id: str | None = None,
) -> list[dict]:
    """Claim local-effect records for a future outbox worker; does not dispatch."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        # A crashed sender may already have reached the receiver. A new lease
        # must not turn uncertainty into permission to send again.
        workspace_scope = " AND workspace_id = ?" if workspace_id is not None else ""
        await db.execute(
            """UPDATE workflow_outbox SET status='needs_review', lease_owner=NULL, lease_until=NULL,
                      updated_at=CURRENT_TIMESTAMP
               WHERE status='sending' AND effect_started_at IS NOT NULL AND lease_until <= ?""" + workspace_scope,
            (now, *((workspace_id,) if workspace_id is not None else ())),
        )
        # See the remote-command claim above: the persisted lease and row lock
        # together prevent two workers from dispatching one effect.
        claim_lock = " FOR UPDATE SKIP LOCKED" if is_postgres() else ""
        async with db.execute(
            """
            SELECT event_id FROM workflow_outbox
            WHERE ((
                status IN ('pending', 'retryable')
                AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
            ) OR (
                status = 'sending' AND lease_until IS NOT NULL AND lease_until <= ?
            ))
            """ + workspace_scope + """
            ORDER BY created_at
            LIMIT ?
            """ + claim_lock,
            (now, now, *((workspace_id,) if workspace_id is not None else ()), int(limit)),
        ) as cursor:
            event_ids = [str(row[0]) for row in await cursor.fetchall()]
        if event_ids:
            placeholders = ", ".join("?" for _ in event_ids)
            await db.execute(
                f"UPDATE workflow_outbox SET status = 'sending', lease_owner = ?, lease_until = ?, attempts = attempts + 1, "
                f"updated_at = CURRENT_TIMESTAMP WHERE event_id IN ({placeholders})" + workspace_scope,
                [lease_owner, lease_until, *event_ids, *((workspace_id,) if workspace_id is not None else ())],
            )
            async with db.execute(
                f"SELECT * FROM workflow_outbox WHERE event_id IN ({placeholders})" + workspace_scope,
                [*event_ids, *((workspace_id,) if workspace_id is not None else ())]
            ) as cursor:
                rows = [dict(row) for row in await cursor.fetchall()]
        else:
            rows = []
        await db.commit()
    return rows


async def begin_workflow_outbox_effect_v2(event_id: str, lease_owner: str, now: str) -> bool:
    """Durably mark the uncertainty boundary before invoking an external sink."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """UPDATE workflow_outbox SET effect_started_at=?, updated_at=CURRENT_TIMESTAMP
               WHERE event_id=? AND status='sending' AND lease_owner=?
                 AND lease_until > ? AND effect_started_at IS NULL""",
            (now, event_id, lease_owner, now),
        )
        await db.commit()
        return cursor.rowcount == 1


async def mark_workflow_outbox_completed_v2(event_id: str, *, lease_owner: str | None = None) -> bool:
    """Record a successfully dispatched local effect exactly once."""
    async with aiosqlite.connect(DB_PATH) as db:
        query = """UPDATE workflow_outbox
                   SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                       lease_owner = NULL, lease_until = NULL, updated_at = CURRENT_TIMESTAMP
                   WHERE event_id = ? AND status = 'sending'"""
        params: list[object] = [event_id]
        if lease_owner is not None:
            query += " AND lease_owner = ?"
            params.append(lease_owner)
        cursor = await db.execute(query, params)
        await db.commit()
    return cursor.rowcount == 1


async def mark_workflow_outbox_retryable_v2(event_id: str, reason: str | None = None, *, lease_owner: str | None = None) -> bool:
    """Release a failed local effect for a later idempotent retry."""
    async with aiosqlite.connect(DB_PATH) as db:
        query = """UPDATE workflow_outbox
                   SET status = 'retryable', lease_owner = NULL, lease_until = NULL, effect_started_at = NULL, next_attempt_at = CURRENT_TIMESTAMP,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE event_id = ? AND status = 'sending'"""
        params: list[object] = [event_id]
        if lease_owner is not None:
            query += " AND lease_owner = ?"
            params.append(lease_owner)
        cursor = await db.execute(query, params)
        await db.commit()
    return cursor.rowcount == 1


async def mark_workflow_outbox_needs_review_v2(
    event_id: str, reason: str | None = None, *, lease_owner: str | None = None
) -> bool:
    """Stop automatic redelivery after an externally ambiguous outcome."""
    async with aiosqlite.connect(DB_PATH) as db:
        query = """UPDATE workflow_outbox
                   SET status = 'needs_review', lease_owner = NULL, lease_until = NULL,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE event_id = ? AND status = 'sending'"""
        params: list[object] = [event_id]
        if lease_owner is not None:
            query += " AND lease_owner = ?"
            params.append(lease_owner)
        cursor = await db.execute(query, params)
        await db.commit()
    return cursor.rowcount == 1


async def hold_legacy_operations_v2(
    *,
    outbox_event_ids: list[str],
    hub_command_ids: list[int],
    reason: str,
    actor_id: str = "system:cutover-hold",
) -> dict[str, int]:
    """Atomically quarantine an explicitly reviewed legacy queue slice.

    This is deliberately an allow-list operation: every requested row must
    still be pending and present, otherwise the transaction rolls back.  The
    previous state and lease/effect markers are retained in the audit event so
    a restart cannot silently re-enqueue the work.  ``needs_review`` is not
    eligible for either Hub-command or Outbox worker claims.
    """
    if not outbox_event_ids and not hub_command_ids:
        return {"outbox_held": 0, "hub_commands_held": 0}
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            outbox_rows: list[dict] = []
            for event_id in outbox_event_ids:
                lock = " FOR UPDATE" if is_postgres() else ""
                row = await (await db.execute(
                    "SELECT event_id, status, attempts, lease_owner, lease_until, effect_started_at, completed_at "
                    "FROM workflow_outbox WHERE event_id=?" + lock,
                    (event_id,),
                )).fetchone()
                if not row or str(row[1]) != "pending":
                    raise ValueError(f"Outbox hold precondition failed for {event_id}")
                outbox_rows.append({
                    "event_id": row[0], "status": row[1], "attempts": row[2],
                    "lease_owner": row[3], "lease_until": row[4],
                    "effect_started_at": row[5], "completed_at": row[6],
                })
            command_rows: list[dict] = []
            for command_id in hub_command_ids:
                lock = " FOR UPDATE" if is_postgres() else ""
                row = await (await db.execute(
                    "SELECT id, status, attempts, lease_owner, lease_expires_at FROM hub_commands WHERE id=?" + lock,
                    (command_id,),
                )).fetchone()
                if not row or str(row[1]) != "pending":
                    raise ValueError(f"Hub command hold precondition failed for {command_id}")
                command_rows.append({
                    "id": row[0], "status": row[1], "attempts": row[2],
                    "lease_owner": row[3], "lease_expires_at": row[4],
                })
            for row in outbox_rows:
                await db.execute(
                    "UPDATE workflow_outbox SET status='needs_review', lease_owner=NULL, lease_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE event_id=? AND status='pending'",
                    (row["event_id"],),
                )
                detail = json.dumps({
                    "source": "explicit_cutover_hold",
                    "previous_status": row["status"],
                    "previous_attempts": row["attempts"],
                    "had_lease": bool(row["lease_owner"] or row["lease_until"]),
                    "effect_started": bool(row["effect_started_at"]),
                    "completed": bool(row["completed_at"]),
                    "reason": str(reason)[:500],
                }, separators=(",", ":"))
                await db.execute(
                    "INSERT INTO audit_events (id, workspace_id, actor_id, action, target_type, target_id, outcome, detail_json) "
                    "SELECT ?, workspace_id, ?, 'queue.hold', 'workflow_outbox', event_id, 'accepted', ? "
                    "FROM workflow_outbox WHERE event_id=?",
                    (str(uuid.uuid4()), actor_id, detail, row["event_id"]),
                )
            for row in command_rows:
                await db.execute(
                    "UPDATE hub_commands SET status='needs_review', lease_owner=NULL, lease_expires_at=NULL, last_error=? WHERE id=? AND status='pending'",
                    (str(reason)[:500], row["id"]),
                )
                detail = json.dumps({
                    "source": "explicit_cutover_hold",
                    "previous_status": row["status"],
                    "previous_attempts": row["attempts"],
                    "had_lease": bool(row["lease_owner"] or row["lease_expires_at"]),
                    "reason": str(reason)[:500],
                }, separators=(",", ":"))
                await db.execute(
                    "INSERT INTO audit_events (id, workspace_id, actor_id, action, target_type, target_id, outcome, detail_json) "
                    "SELECT ?, workspace_id, ?, 'queue.hold', 'hub_command', CAST(id AS TEXT), 'accepted', ? "
                    "FROM hub_commands WHERE id=?",
                    (str(uuid.uuid4()), actor_id, detail, row["id"]),
                )
            await db.commit()
            return {"outbox_held": len(outbox_rows), "hub_commands_held": len(command_rows)}
        except Exception:
            await db.rollback()
            raise


async def renew_workflow_outbox_lease_v2(event_id: str, lease_owner: str, lease_until: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """UPDATE workflow_outbox SET lease_until=?, updated_at=CURRENT_TIMESTAMP
               WHERE event_id=? AND status='sending' AND lease_owner=?""",
            (lease_until, event_id, lease_owner),
        )
        await db.commit()
    return cursor.rowcount == 1


async def list_recovery_matches_v2() -> list[dict]:
    """Durable workflow rows needed to restore timers/threads after a restart."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT m.*, COALESCE(t.provider_type, 'startgg') AS provider_type
               FROM active_matches m LEFT JOIN tournaments t ON t.slug=m.tournament_slug
               WHERE m.hub_status IN ('called', 'ready', 'in_progress')
                  OR m.status IN ('called', 'in_progress')"""
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_live_sync_state_v2(tournament_slug: str, workspace_id: str | None = None) -> dict | None:
    """Read-only scheduler state derived from the durable projection."""
    tournament = await get_tournament(tournament_slug, workspace_id)
    if not tournament:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT
                 SUM(CASE WHEN COALESCE(hub_status, status)='in_progress' THEN 1 ELSE 0 END),
                 SUM(CASE WHEN COALESCE(hub_status, status) IN ('called', 'ready') THEN 1 ELSE 0 END),
                 SUM(CASE WHEN sync_status IN ('pending', 'acknowledged_unverified', 'retrying') THEN 1 ELSE 0 END)
               FROM active_matches WHERE tournament_slug=?
                 AND (CAST(? AS TEXT) IS NULL OR workspace_id=?)""",
            (tournament_slug, workspace_id, workspace_id),
        ) as cursor:
            active, called, pending = await cursor.fetchone()
    try:
        raw = json.loads(tournament.get("raw_data") or "{}")
    except (TypeError, json.JSONDecodeError):
        raw = {}
    terminal = str(raw.get("provider_state") or "").lower() in {"complete", "completed", "finalized", "awaiting_review"}
    return {
        "mode": tournament.get("challonge_sync_mode") or "economy",
        "completed": terminal,
        "archived": bool(tournament.get("archived", False)),
        "active_match": bool(active), "called_match": bool(called),
        "pending_verification": bool(pending),
    }


async def list_challonge_state_repair_rows_v2() -> list[dict]:
    """Read repair candidates plus only the local evidence needed for a dry run."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT m.*, t.name AS tournament_name, t.provider_type,
                 EXISTS(SELECT 1 FROM provider_reconciliation_audit a
                        WHERE a.set_id=m.set_id AND a.provider_type='challonge'
                          AND a.action IN ('call', 'ready', 'start', 'assign_station')) AS has_local_audit
               FROM active_matches m JOIN tournaments t ON t.slug=m.tournament_slug
               WHERE t.provider_type='challonge'
               ORDER BY m.tournament_slug, m.set_id"""
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def save_challonge_state_repair_report_v2(report: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO challonge_state_repair_reports
               (report_id, snapshot_id, snapshot_observed_at, fingerprint, report_json)
               VALUES (?, ?, ?, ?, ?)""",
            (report["report_id"], report["snapshot_id"], report["snapshot_observed_at"],
             report["fingerprint"], json.dumps(report)),
        )
        await db.commit()


async def get_challonge_state_repair_report_v2(report_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM challonge_state_repair_reports WHERE report_id=?", (report_id,)) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def apply_challonge_state_repair_v2(report_id: str, fingerprint: str, approved_set_ids: list[str], *, applied_by: str) -> int:
    """Apply an approved dry run only if its exact immutable report still matches."""
    stored = await get_challonge_state_repair_report_v2(report_id)
    if not stored or stored["fingerprint"] != fingerprint:
        raise ValueError("Repair report changed or is unavailable; run a new dry run.")
    report = json.loads(stored["report_json"])
    eligible_rows = {row["match_key"]: row for row in report.get("rows", []) if row.get("eligibility") == "eligible"}
    eligible = set(eligible_rows)
    requested = set(approved_set_ids)
    if not requested or not requested.issubset(eligible):
        raise ValueError("Approved rows do not exactly match eligible rows in the dry run.")
    if stored.get("applied_at"):
        # An applied immutable report is intentionally idempotent.  It must not
        # acquire a second audit entry or rewrite a later Hub workflow state.
        return 0
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            count = 0
            for set_id in requested:
                report_row = eligible_rows[set_id]
                raw_state = report_row["provider_raw_state"]
                normalized_state = report_row["provider_normalized_state"]
                # Re-check every locally observable precondition while holding the
                # write lease.  A report is evidence, not permission to overwrite
                # a match that was called, scored, or started after its dry run.
                async with db.execute(
                    """SELECT m.tournament_slug, m.status
                       FROM active_matches m
                       JOIN tournaments t ON t.slug=m.tournament_slug
                       WHERE m.set_id=? AND t.provider_type='challonge'
                         AND m.status='in_progress'
                         AND (m.provider_state_raw IS NULL OR m.provider_state_raw=?)
                         AND (m.provider_state_normalized IS NULL OR m.provider_state_normalized=?)
                         AND m.called_at IS NULL AND m.station_id IS NULL
                         AND m.discord_thread_id IS NULL
                         AND COALESCE(m.p1_ready, FALSE)=FALSE AND COALESCE(m.p2_ready, FALSE)=FALSE
                         AND (m.p1_score IS NULL OR m.p1_score=0)
                         AND (m.p2_score IS NULL OR m.p2_score=0)
                         AND COALESCE(m.result_kind, '')=''
                         AND NOT EXISTS(
                           SELECT 1 FROM provider_reconciliation_audit a
                           WHERE a.set_id=m.set_id AND a.provider_type='challonge'
                             AND a.action IN ('call', 'ready', 'start', 'assign_station')
                         )""",
                    (set_id, raw_state, normalized_state),
                ) as cursor:
                    before = await cursor.fetchone()
                if not before:
                    raise ValueError("Repair preconditions changed; run a new dry run before applying.")
                await db.execute(
                    """UPDATE active_matches SET status='not_started', hub_status='not_started',
                       hub_status_origin='migration', sync_status='synced', sync_reason='Approved false-live repair',
                       provider_state_raw=?, provider_state_normalized=?
                       WHERE set_id=? AND tournament_slug=? AND status='in_progress'""",
                    (raw_state, normalized_state, set_id, before["tournament_slug"]),
                )
                count += 1
                await db.execute(
                    """INSERT INTO provider_reconciliation_audit
                       (tournament_slug, set_id, provider_type, action, before_hub_status, after_hub_status,
                        provider_state_raw, reason)
                       VALUES (?, ?, 'challonge', 'state_repair_apply', ?, 'not_started', ?,
                               'Approved immutable dry-run report')""",
                    (before["tournament_slug"], set_id, before["status"], raw_state),
                )
            if count != len(requested):
                raise ValueError("Repair did not cover every approved row; no changes were applied.")
            await db.execute("UPDATE challonge_state_repair_reports SET applied_at=CURRENT_TIMESTAMP, applied_by=? WHERE report_id=?", (applied_by, report_id))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return count


async def apply_local_workflow_transition_v2(
    match_id: str,
    hub_status: str,
    action: str,
    *,
    legacy_status: str | None = None,
    fields: dict | None = None,
    effects: list[dict] | None = None,
) -> dict:
    """Commit one Hub-local transition, audit record, and effects atomically.

    This is the only Phase-7A writer used for the new Challonge local workflow.
    It has no provider dependency: provider-owned fields are read only and every
    external Discord/OBS intent is persisted in ``workflow_outbox`` before a
    worker may dispatch it.
    """
    requested = dict(fields or {})
    effects = list(effects or [])
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            # The tournament is left-joined and may be absent on legacy data;
            # PostgreSQL can only lock the concrete match relation.
            match_lock = " FOR UPDATE OF m" if is_postgres() else ""
            async with db.execute(
                """SELECT m.*, COALESCE(t.provider_type, 'startgg') AS owner_provider
                   FROM active_matches m LEFT JOIN tournaments t ON t.slug = m.tournament_slug
                   WHERE m.set_id = ?""" + match_lock,
                (match_id,),
            ) as cursor:
                match = await cursor.fetchone()
            if not match:
                raise ValueError(f"Unknown match: {match_id}")
            match = dict(match)
            if match["owner_provider"] != "challonge":
                raise ValueError("Local workflow transition is only valid for Challonge")

            async with db.execute("PRAGMA table_info(active_matches)") as cursor:
                valid_columns = {row[1] for row in await cursor.fetchall()}
            update = {key: value for key, value in requested.items() if key in valid_columns}
            update.update({
                "status": legacy_status or hub_status,
                "hub_status": hub_status,
                "hub_status_origin": "local_workflow",
                "sync_status": "local_only",
            })

            station_id = update.get("station_id")
            if station_id:
                station_lock = " FOR UPDATE" if is_postgres() else ""
                async with db.execute(
                    "SELECT active_match_id FROM stations WHERE id = ?" + station_lock,
                    (station_id,),
                ) as cursor:
                    station = await cursor.fetchone()
                if not station:
                    raise ValueError("Station was not found")
                owner = station["active_match_id"]
                if owner and owner != match_id:
                    # A prior match may have been removed or completed while
                    # its station pointer remained behind.  Treat only a
                    # currently live match as an occupation; clear a stale
                    # owner inside this same transaction so assignment can be
                    # retried safely after restart.  A live owner (including a
                    # different workspace) still blocks the operation.
                    async with db.execute(
                        "SELECT status, workspace_id FROM active_matches WHERE set_id = ?",
                        (owner,),
                    ) as owner_cursor:
                        owner_row = await owner_cursor.fetchone()
                    if owner_row and str(owner_row["status"] or "") in {"called", "in_progress"}:
                        raise ValueError("Station is already occupied")
                    await db.execute(
                        "UPDATE stations SET active_match_id = NULL WHERE id = ? AND active_match_id = ?",
                        (station_id, owner),
                    )
                async with db.execute(
                    """SELECT set_id FROM active_matches
                       WHERE station_id = ? AND set_id != ?
                         AND status IN ('called', 'in_progress') LIMIT 1""",
                    (station_id, match_id),
                ) as cursor:
                    conflicting_match = await cursor.fetchone()
                if conflicting_match:
                    raise ValueError("Station is already occupied")
                await db.execute("UPDATE stations SET active_match_id = ? WHERE id = ?", (match_id, station_id))

            assignments = ", ".join(f'"{key}" = ?' for key in update)
            await db.execute(
                f"UPDATE active_matches SET {assignments} WHERE set_id = ?",
                [*update.values(), match_id],
            )
            await db.execute(
                """INSERT INTO provider_reconciliation_audit (
                       tournament_slug, set_id, provider_type, action, before_hub_status,
                       after_hub_status, provider_state_raw, reason
                   ) VALUES (?, ?, 'challonge', ?, ?, ?, ?, ?)""",
                (
                    match.get("tournament_slug") or "", match_id, action,
                    match.get("hub_status") or match.get("status"), hub_status,
                    match.get("provider_state_raw"), "Hub-owned local workflow",
                ),
            )
            for event in effects:
                dedupe = event.get("deduplication_key")
                if not dedupe:
                    raise ValueError("Workflow outbox event requires deduplication_key")
                await db.execute(
                    """INSERT INTO workflow_outbox (
                           event_id, match_id, event_type, payload_json, deduplication_key,
                           status, attempts, next_attempt_at, workspace_id
                       ) VALUES (?, ?, ?, ?, ?, 'pending', 0, NULL, ?)
                       ON CONFLICT(deduplication_key) DO NOTHING""",
                    (
                        event.get("event_id") or str(uuid.uuid4()), match_id,
                        event["event_type"], json.dumps(event.get("payload", {})), dedupe,
                        match.get("workspace_id"),
                    ),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return await get_active_match(match_id) or {}


async def complete_match_and_enqueue_effects_v2(
    match_id: str,
    result_kind: str,
    *,
    dq_player: str | None = None,
    p1_score: int | None = None,
    p2_score: int | None = None,
) -> dict:
    """Idempotently complete a match and free only its own station."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute("SELECT * FROM active_matches WHERE set_id = ?", (match_id,)) as cursor:
                match = await cursor.fetchone()
            if not match:
                raise ValueError(f"Unknown match: {match_id}")
            match = dict(match)
            # A legacy writer can leave the axes split (for example
            # ``status=called`` while a verified command marked Hub complete).
            # Treat completion as idempotent only when *both* representations
            # agree; otherwise repair the projection without duplicating the
            # deduplicated outbox effects below.
            if match.get("hub_status") == "complete" and match.get("status") == "complete":
                await db.commit()
                return {"completed": False, "already_complete": True}

            station_released = False
            station_id = match.get("station_id")
            if station_id:
                async with db.execute("SELECT active_match_id FROM stations WHERE id = ?", (station_id,)) as cursor:
                    station = await cursor.fetchone()
                if station and station["active_match_id"] == match_id:
                    await db.execute("UPDATE stations SET active_match_id = NULL WHERE id = ?", (station_id,))
                    station_released = True

            await db.execute(
                """UPDATE active_matches
                   SET status='complete', hub_status='complete', hub_status_origin='remote_mutation',
                       result_kind=?, dq_player=COALESCE(?, dq_player),
                       p1_score=COALESCE(?, p1_score), p2_score=COALESCE(?, p2_score),
                       station_id=CASE WHEN ? THEN NULL ELSE station_id END
                   WHERE set_id=?""",
                (result_kind, dq_player, p1_score, p2_score, station_released, match_id),
            )
            await db.execute(
                """INSERT INTO provider_reconciliation_audit (
                       tournament_slug, set_id, provider_type, action, before_hub_status,
                       after_hub_status, provider_state_raw, reason
                   ) VALUES (?, ?, 'challonge', 'complete_match', ?, 'complete', ?, ?)""",
                (
                    match.get("tournament_slug") or "", match_id,
                    match.get("hub_status") or match.get("status"), match.get("provider_state_raw"),
                    "Idempotent completion service",
                ),
            )
            for event_type in ("discord_match_complete", "obs_match_complete", "next_match_discovery"):
                await db.execute(
                    """INSERT INTO workflow_outbox (
                           event_id, match_id, event_type, payload_json, deduplication_key,
                           status, attempts, workspace_id
                       ) VALUES (?, ?, ?, '{}', ?, 'pending', 0, ?)
                       ON CONFLICT(deduplication_key) DO NOTHING""",
                    (str(uuid.uuid4()), match_id, event_type, f"{event_type}:{match_id}", match.get("workspace_id")),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return {"completed": True, "already_complete": False, "station_released": station_released}


async def upsert_provider_identity_link_v2(link: dict, workspace_id: str | None = None) -> dict:
    """Persist a stable provider entrant/participant → Discord mapping.

    Display names are audit metadata only and are deliberately not used as a
    lookup key, preventing a same-name player from receiving a match call.
    """
    required = {"provider_type", "tournament_slug", "verification_state"}
    missing = required - link.keys()
    if missing:
        raise ValueError(f"Missing identity link fields: {', '.join(sorted(missing))}")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO provider_identity_links (
                   workspace_id, provider_type, provider_participant_id, provider_entrant_id,
                   aitob_participant_id, discord_user_id, discord_role_id,
                   tournament_slug, scope, verification_state, source,
                   display_name_snapshot, aliases_json, verified_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT DO NOTHING""",
            (
                workspace_id, link["provider_type"], link.get("provider_participant_id"), link.get("provider_entrant_id"),
                link.get("aitob_participant_id"), link.get("discord_user_id"), link.get("discord_role_id"),
                link["tournament_slug"], link.get("scope", "tournament"), link["verification_state"],
                link.get("source", "organizer_override"), link.get("display_name_snapshot"),
                json.dumps(link.get("aliases", [])), link.get("verified_at"),
            ),
        )
        async with db.execute(
            """SELECT * FROM provider_identity_links
               WHERE provider_type=? AND tournament_slug=?
                 AND (CAST(? AS TEXT) IS NULL OR workspace_id=CAST(? AS TEXT))
                 AND COALESCE(provider_entrant_id, '')=COALESCE(CAST(? AS TEXT), '')
                 AND COALESCE(discord_user_id, '')=COALESCE(CAST(? AS TEXT), '')
               ORDER BY id DESC LIMIT 1""",
            (link["provider_type"], link["tournament_slug"], workspace_id, workspace_id, link.get("provider_entrant_id"), link.get("discord_user_id")),
        ) as cursor:
            row = await cursor.fetchone()
        await db.commit()
    return dict(row) if row else {}


async def get_verified_discord_identity_link_v2(provider_type: str, tournament_slug: str, entrant_id: str, workspace_id: str | None = None) -> dict | None:
    """Return only explicitly verified/overridden identity links by stable ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM provider_identity_links
               WHERE provider_type=? AND tournament_slug=? AND provider_entrant_id=?
                 AND (CAST(? AS TEXT) IS NULL OR workspace_id=CAST(? AS TEXT))
                 AND verification_state IN ('verified', 'organizer_override')
                 AND discord_user_id IS NOT NULL
               ORDER BY verified_at DESC, id DESC LIMIT 1""",
            (provider_type, tournament_slug, entrant_id, workspace_id, workspace_id),
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def upsert_provider_api_budget_v2(
    provider_type: str, provider_account_id: str, **values
) -> None:
    """Persist V2 budget state without scheduling a provider request."""
    allowed = {
        "window_started_at", "estimated_used", "remaining_if_known", "reset_at",
        "backoff_until", "last_429_at",
    }
    data = {key: value for key, value in values.items() if key in allowed}
    if not data:
        return
    columns = ["provider_type", "provider_account_id", *data.keys()]
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{key} = excluded.{key}" for key in data)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT INTO provider_api_budgets ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(provider_type, provider_account_id) DO UPDATE SET {updates}, "
            "updated_at = CURRENT_TIMESTAMP",
            [provider_type, provider_account_id, *data.values()],
        )
        await db.commit()


async def save_provider_snapshot_cache_v2(
    provider_type: str,
    provider_account_id: str,
    tournament_slug: str,
    scope: str,
    *,
    entity_coverage: list[str] | None = None,
    revision: str | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    content_hash: str | None = None,
    payload: dict | None = None,
    expires_at: str | None = None,
) -> None:
    """Store V2 cache metadata only; no provider request is made here."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO provider_snapshot_cache (
                provider_type, provider_account_id, tournament_slug, scope,
                entity_coverage_json, revision, etag, last_modified, content_hash,
                payload_json, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_type, provider_account_id, tournament_slug, scope)
            DO UPDATE SET
                entity_coverage_json = excluded.entity_coverage_json,
                revision = excluded.revision,
                etag = excluded.etag,
                last_modified = excluded.last_modified,
                content_hash = excluded.content_hash,
                payload_json = excluded.payload_json,
                expires_at = excluded.expires_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                provider_type, provider_account_id, tournament_slug, scope,
                json.dumps(entity_coverage or []), revision, etag, last_modified,
                content_hash, json.dumps(payload or {}), expires_at,
            ),
        )
        await db.commit()


async def record_provider_request_telemetry_v2(
    provider_type: str,
    provider_account_id: str,
    tournament_slug: str,
    scope: str,
    priority: int,
    disposition: str,
    *,
    cost_class: str | None = None,
) -> None:
    """Persist coordinator admission telemetry; this function never contacts a provider."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO provider_request_telemetry (
                provider_type, provider_account_id, tournament_slug, scope,
                priority, disposition, cost_class
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider_type, provider_account_id, tournament_slug, scope,
                int(priority), disposition, cost_class,
            ),
        )
        await db.commit()
