"""Workspace-scoped repositories for player profiles, provider identities,

game preferences, character defaults, and scoped tournament overrides.
"""

from __future__ import annotations

import uuid
from typing import Any
from backend.core.storage import dbapi, Row
from backend.core import database


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Player Profiles ─────────────────────────────────────────────────────────

async def create_player_profile(
    workspace_id: str,
    display_name: str,
    prefix: str | None = None,
    country: str | None = None,
    avatar_url: str | None = None,
    discord_id: str | None = None,
    notes: str | None = None,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Create a workspace-scoped player profile."""
    pid = profile_id or _uuid()
    clean_name = display_name.strip()
    clean_prefix = prefix.strip() if prefix else None
    clean_country = country.strip() if country else None
    clean_avatar = avatar_url.strip() if avatar_url else None
    clean_discord = discord_id.strip() if discord_id else None
    clean_notes = notes.strip() if notes else None

    async with dbapi.connect(database.DATABASE_DSN) as db:
        if clean_discord and profile_id is None:
            # Discord is the durable identity received at registration. Reuse
            # the archive record instead of silently creating a second card.
            row = await (await db.execute(
                """INSERT INTO player_profiles (
                    id, workspace_id, display_name, prefix, country, avatar_url, discord_id, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (workspace_id, discord_id) WHERE discord_id IS NOT NULL
                DO UPDATE SET updated_at = player_profiles.updated_at
                RETURNING id""",
                (pid, workspace_id, clean_name, clean_prefix, clean_country, clean_avatar, clean_discord, clean_notes),
            )).fetchone()
            pid = str(row[0])
        else:
            await db.execute(
                """INSERT INTO player_profiles (
                    id, workspace_id, display_name, prefix, country, avatar_url, discord_id, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (workspace_id, id) DO UPDATE SET
                    display_name = excluded.display_name,
                    prefix = excluded.prefix,
                    country = excluded.country,
                    avatar_url = excluded.avatar_url,
                    discord_id = excluded.discord_id,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (pid, workspace_id, clean_name, clean_prefix, clean_country, clean_avatar, clean_discord, clean_notes),
            )
        await db.commit()
    return await get_player_profile(pid, workspace_id) or {}


async def get_player_profile(profile_id: str, workspace_id: str) -> dict[str, Any] | None:
    """Retrieve a single player profile by ID within a workspace."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT * FROM player_profiles WHERE id = ? AND workspace_id = ?",
            (profile_id, workspace_id),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_player_profile_by_discord_id(discord_id: str, workspace_id: str) -> dict[str, Any] | None:
    """Find a player profile associated with a Discord ID in a workspace."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT * FROM player_profiles WHERE discord_id = ? AND workspace_id = ?",
            (discord_id, workspace_id),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def list_player_profiles(
    workspace_id: str,
    limit: int = 100,
    offset: int = 0,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """List player profiles in a workspace with optional name search and pagination."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        sql = "SELECT * FROM player_profiles WHERE workspace_id = ?"
        params: list[Any] = [workspace_id]
        if query and query.strip():
            sql += " AND (display_name ILIKE ? OR prefix ILIKE ?)"
            params.extend([f"%{query.strip()}%", f"%{query.strip()}%"])
        sql += " ORDER BY display_name ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_player_profile(
    profile_id: str,
    workspace_id: str,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """Update editable fields of a player profile."""
    allowed = {"display_name", "prefix", "country", "avatar_url", "discord_id", "notes"}
    fields: list[str] = []
    params: list[Any] = []
    for key, value in data.items():
        if key in allowed:
            fields.append(f"{key} = ?")
            params.append(value.strip() if isinstance(value, str) else value)
    if not fields:
        return await get_player_profile(profile_id, workspace_id)

    requested_discord_id = next(
        (str(value).strip() for key, value in data.items() if key == "discord_id" and value),
        None,
    )
    if requested_discord_id:
        async with dbapi.connect(database.DATABASE_DSN) as db:
            row = await (await db.execute(
                "SELECT id FROM player_profiles WHERE workspace_id=? AND discord_id=?",
                (workspace_id, requested_discord_id),
            )).fetchone()
        if row and str(row[0]) != profile_id:
            raise ValueError("Discord is already linked to another Player Archive profile")

    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([profile_id, workspace_id])
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            f"UPDATE player_profiles SET {', '.join(fields)} WHERE id = ? AND workspace_id = ?",
            params,
        )
        # Tournament rows are a scoped presentation projection, not a second
        # player record. Keep fields edited in Player Archive reflected in the
        # already-linked entrants that still carry a scoped presentation row.
        override_fields: list[str] = []
        override_values: list[Any] = []
        field_map = {
            "display_name": "display_name",
            "prefix": "prefix",
            "country": "country",
            "avatar_url": "avatar_url",
        }
        for key, column in field_map.items():
            if key in data:
                override_fields.append(f"{column} = ?")
                value = data[key]
                override_values.append(value.strip() if isinstance(value, str) else value)
        if override_fields:
            await db.execute(
                f"""UPDATE tournament_entrant_overrides o
                       SET {', '.join(override_fields)}, updated_at = CURRENT_TIMESTAMP
                     WHERE o.workspace_id = ?
                       AND EXISTS (
                           SELECT 1 FROM tournament_player_links l
                            WHERE l.workspace_id = o.workspace_id
                              AND l.tournament_slug = o.tournament_slug
                              AND l.entrant_id = o.entrant_id
                              AND l.player_profile_id = ?
                       )""",
                override_values + [workspace_id, profile_id],
            )
        await db.commit()
    return await get_player_profile(profile_id, workspace_id)


async def delete_player_profile(profile_id: str, workspace_id: str) -> bool:
    """Delete a player profile and cascade associations."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "DELETE FROM player_profiles WHERE id = ? AND workspace_id = ?",
            (profile_id, workspace_id),
        ) as cursor:
            count = cursor.rowcount
        await db.commit()
        return count > 0


# ── Provider Identities ─────────────────────────────────────────────────────

async def add_provider_identity(
    workspace_id: str,
    player_profile_id: str,
    provider: str,
    provider_user_id: str,
    provider_gamer_tag: str | None = None,
    verified: bool = True,
) -> dict[str, Any]:
    """Link a provider account identity to a player profile."""
    ident_id = _uuid()
    clean_provider = provider.strip().lower()
    clean_uid = str(provider_user_id).strip()
    clean_tag = provider_gamer_tag.strip() if provider_gamer_tag else None

    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT 1 FROM player_profiles WHERE id = ? AND workspace_id = ?",
            (player_profile_id, workspace_id),
        ) as cursor:
            if not await cursor.fetchone():
                raise ValueError("Player profile not found in this workspace")
        async with db.execute(
            """SELECT player_profile_id FROM player_provider_identities
               WHERE workspace_id = ? AND provider = ? AND provider_user_id = ?""",
            (workspace_id, clean_provider, clean_uid),
        ) as cursor:
            existing = await cursor.fetchone()
        if existing and existing[0] != player_profile_id:
            raise ValueError("Provider identity is already linked to another player profile")
        await db.execute(
            """INSERT INTO player_provider_identities (
                id, workspace_id, player_profile_id, provider, provider_user_id, provider_gamer_tag, verified, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (workspace_id, provider, provider_user_id) DO UPDATE SET
                provider_gamer_tag = excluded.provider_gamer_tag,
                verified = excluded.verified,
                updated_at = CURRENT_TIMESTAMP
            """,
            (ident_id, workspace_id, player_profile_id, clean_provider, clean_uid, clean_tag, verified),
        )
        await db.commit()

        async with db.execute(
            "SELECT * FROM player_provider_identities WHERE workspace_id = ? AND provider = ? AND provider_user_id = ?",
            (workspace_id, clean_provider, clean_uid),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}


async def list_provider_identities(workspace_id: str, player_profile_id: str) -> list[dict[str, Any]]:
    """List all provider identities linked to a player profile."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT * FROM player_provider_identities WHERE workspace_id = ? AND player_profile_id = ? ORDER BY provider ASC",
            (workspace_id, player_profile_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def find_profile_by_provider_identity(
    workspace_id: str,
    provider: str,
    provider_user_id: str,
) -> dict[str, Any] | None:
    """Look up a player profile using a provider identity."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            """SELECT p.* FROM player_profiles p
               JOIN player_provider_identities i ON i.player_profile_id = p.id AND i.workspace_id = p.workspace_id
               WHERE i.workspace_id = ? AND i.provider = ? AND i.provider_user_id = ?""",
            (workspace_id, provider.strip().lower(), str(provider_user_id).strip()),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ── Game Profiles & Character Defaults ──────────────────────────────────────

async def set_player_game_profile(
    workspace_id: str,
    player_profile_id: str,
    game_id: str,
    in_game_name: str | None = None,
    in_game_id: str | None = None,
) -> dict[str, Any]:
    """Create or update a player's game-specific profile."""
    gid = _uuid()
    clean_game = game_id.strip()
    clean_ign = in_game_name.strip() if in_game_name else None
    clean_cfn = in_game_id.strip() if in_game_id else None

    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT 1 FROM player_profiles WHERE id = ? AND workspace_id = ?",
            (player_profile_id, workspace_id),
        ) as cursor:
            if not await cursor.fetchone():
                raise ValueError("Player profile not found in this workspace")
        await db.execute(
            """INSERT INTO player_game_profiles (
                id, workspace_id, player_profile_id, game_id, in_game_name, in_game_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (workspace_id, player_profile_id, game_id) DO UPDATE SET
                in_game_name = excluded.in_game_name,
                in_game_id = excluded.in_game_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (gid, workspace_id, player_profile_id, clean_game, clean_ign, clean_cfn),
        )
        await db.commit()

        async with db.execute(
            "SELECT * FROM player_game_profiles WHERE workspace_id = ? AND player_profile_id = ? AND game_id = ?",
            (workspace_id, player_profile_id, clean_game),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}


async def get_player_game_profile(
    workspace_id: str,
    player_profile_id: str,
    game_id: str,
) -> dict[str, Any] | None:
    """Retrieve a game profile for a player."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT * FROM player_game_profiles WHERE workspace_id = ? AND player_profile_id = ? AND game_id = ?",
            (workspace_id, player_profile_id, game_id.strip()),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def list_player_game_profiles(workspace_id: str, player_profile_id: str) -> list[dict[str, Any]]:
    """List all game profiles for a player."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT * FROM player_game_profiles WHERE workspace_id = ? AND player_profile_id = ? ORDER BY game_id ASC",
            (workspace_id, player_profile_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def set_player_character_default(
    workspace_id: str,
    player_game_profile_id: str,
    character_id: str,
    character_name: str,
    character_image_url: str | None = None,
    is_primary: bool = True,
) -> dict[str, Any]:
    """Set a default character choice for a player game profile."""
    cid = _uuid()
    clean_char_id = str(character_id).strip()
    clean_char_name = character_name.strip()
    clean_char_image = character_image_url.strip() if character_image_url else None

    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            """SELECT 1 FROM player_game_profiles
               WHERE id = ? AND workspace_id = ?""",
            (player_game_profile_id, workspace_id),
        ) as cursor:
            if not await cursor.fetchone():
                raise ValueError("Player game profile not found in this workspace")
        if is_primary:
            await db.execute(
                "UPDATE player_character_defaults SET is_primary = FALSE WHERE workspace_id = ? AND player_game_profile_id = ?",
                (workspace_id, player_game_profile_id),
            )
        await db.execute(
            """INSERT INTO player_character_defaults (
                id, workspace_id, player_game_profile_id, character_id, character_name, character_image_url, is_primary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (workspace_id, player_game_profile_id, character_id) DO UPDATE SET
                character_name = excluded.character_name,
                character_image_url = excluded.character_image_url,
                is_primary = excluded.is_primary
            """,
            (cid, workspace_id, player_game_profile_id, clean_char_id, clean_char_name, clean_char_image, is_primary),
        )
        # Mirror the saved default to linked tournament projections for the
        # same game. The profile remains the durable source of the choice.
        if is_primary:
            await db.execute(
                """UPDATE tournament_entrant_overrides o
                       SET character_id = ?, character_name = ?, character_image_url = ?, updated_at = CURRENT_TIMESTAMP
                      FROM player_game_profiles gp, tournaments t
                     WHERE gp.id = ?
                       AND gp.workspace_id = ?
                       AND t.slug = o.tournament_slug
                       AND t.game = gp.game_id
                       AND o.workspace_id = gp.workspace_id
                       AND EXISTS (
                           SELECT 1 FROM tournament_player_links l
                            WHERE l.workspace_id = o.workspace_id
                              AND l.tournament_slug = o.tournament_slug
                              AND l.entrant_id = o.entrant_id
                              AND l.player_profile_id = gp.player_profile_id
                       )""",
                (clean_char_id, clean_char_name, clean_char_image, player_game_profile_id, workspace_id),
            )
        await db.commit()

        async with db.execute(
            "SELECT * FROM player_character_defaults WHERE workspace_id = ? AND player_game_profile_id = ? AND character_id = ?",
            (workspace_id, player_game_profile_id, clean_char_id),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}


async def get_player_character_defaults(
    workspace_id: str,
    player_game_profile_id: str,
) -> list[dict[str, Any]]:
    """List character defaults for a game profile."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT * FROM player_character_defaults WHERE workspace_id = ? AND player_game_profile_id = ? ORDER BY is_primary DESC, created_at ASC",
            (workspace_id, player_game_profile_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ── Tournament Entrant Overrides ───────────────────────────────────────────

async def set_tournament_entrant_override(
    workspace_id: str,
    provider: str,
    tournament_slug: str,
    event_id: str,
    entrant_id: str,
    data: dict[str, Any],
    updated_by: str | None = None,
) -> dict[str, Any]:
    """Create or update an event-scoped tournament entrant override with row-locking and audit metadata."""
    clean_provider = provider.strip().lower()
    clean_slug = tournament_slug.strip()
    clean_event = str(event_id).strip()
    clean_entrant = str(entrant_id).strip()

    name = data.get("name") if "name" in data else data.get("display_name")
    prefix = data.get("prefix") if "prefix" in data else data.get("team")
    country = data.get("country")
    avatar_url = data.get("avatar_url")
    char_id = data.get("character_id")
    char_name = data.get("character") if "character" in data else data.get("character_name")
    char_image = data.get("character_image_url")
    notes = data.get("notes")

    async with dbapi.connect(database.DATABASE_DSN) as db:
        oid = _uuid()
        await db.execute(
            """INSERT INTO tournament_entrant_overrides (
                id, workspace_id, provider, tournament_slug, event_id, entrant_id,
                display_name, prefix, country, avatar_url, character_id, character_name, character_image_url,
                notes, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (workspace_id, provider, tournament_slug, event_id, entrant_id) DO UPDATE SET
                display_name = CASE WHEN ? THEN excluded.display_name ELSE tournament_entrant_overrides.display_name END,
                prefix = CASE WHEN ? THEN excluded.prefix ELSE tournament_entrant_overrides.prefix END,
                country = CASE WHEN ? THEN excluded.country ELSE tournament_entrant_overrides.country END,
                avatar_url = CASE WHEN ? THEN excluded.avatar_url ELSE tournament_entrant_overrides.avatar_url END,
                character_id = CASE WHEN ? THEN excluded.character_id ELSE tournament_entrant_overrides.character_id END,
                character_name = CASE WHEN ? THEN excluded.character_name ELSE tournament_entrant_overrides.character_name END,
                character_image_url = CASE WHEN ? THEN excluded.character_image_url ELSE tournament_entrant_overrides.character_image_url END,
                notes = CASE WHEN ? THEN excluded.notes ELSE tournament_entrant_overrides.notes END,
                updated_by = CASE WHEN ? THEN excluded.updated_by ELSE tournament_entrant_overrides.updated_by END,
                updated_at = CURRENT_TIMESTAMP""",
            (
                oid, workspace_id, clean_provider, clean_slug, clean_event, clean_entrant,
                name, prefix, country, avatar_url, char_id, char_name, char_image,
                notes, updated_by,
                bool("name" in data or "display_name" in data),
                bool("prefix" in data or "team" in data),
                bool("country" in data),
                bool("avatar_url" in data),
                bool("character_id" in data),
                bool("character" in data or "character_name" in data),
                bool("character_image_url" in data),
                bool("notes" in data),
                bool(updated_by),
            ),
        )
        await db.commit()

    return await get_tournament_entrant_override(workspace_id, clean_provider, clean_slug, clean_event, clean_entrant) or {}


async def get_tournament_entrant_override(
    workspace_id: str,
    provider: str,
    tournament_slug: str,
    event_id: str,
    entrant_id: str,
) -> dict[str, Any] | None:
    """Retrieve an event-scoped entrant override."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            """SELECT * FROM tournament_entrant_overrides
               WHERE workspace_id = ? AND provider = ? AND tournament_slug = ? AND event_id = ? AND entrant_id = ?""",
            (workspace_id, provider.strip().lower(), tournament_slug.strip(), str(event_id).strip(), str(entrant_id).strip()),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_tournament_entrant_override(
    workspace_id: str,
    provider: str,
    tournament_slug: str,
    event_id: str,
    entrant_id: str,
) -> bool:
    """Delete a scoped tournament entrant override (reset to profile/provider)."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            """DELETE FROM tournament_entrant_overrides
               WHERE workspace_id = ? AND provider = ? AND tournament_slug = ? AND event_id = ? AND entrant_id = ?""",
            (workspace_id, provider.strip().lower(), tournament_slug.strip(), str(event_id).strip(), str(entrant_id).strip()),
        ) as cursor:
            count = cursor.rowcount
        await db.commit()
        return count > 0


async def list_tournament_entrant_overrides(
    workspace_id: str,
    tournament_slug: str,
    event_id: str | None = None,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    """List scoped overrides for a tournament, optionally scoped to an event."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        sql = "SELECT * FROM tournament_entrant_overrides WHERE workspace_id = ? AND tournament_slug = ?"
        params: list[Any] = [workspace_id, tournament_slug.strip()]
        if event_id:
            sql += " AND event_id = ?"
            params.append(str(event_id).strip())
        if provider:
            sql += " AND provider = ?"
            params.append(provider.strip().lower())
        sql += " ORDER BY entrant_id ASC"

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ── Entrant Link Resolution ─────────────────────────────────────────────────

async def get_entrant_linked_profile(
    workspace_id: str,
    tournament_slug: str,
    entrant_id: str,
) -> dict[str, Any] | None:
    """Retrieve the confirmed linked PlayerProfile for an entrant."""
    async with dbapi.connect(database.DATABASE_DSN) as db:
        # Tournament links point to the workspace Player Archive.  The legacy
        # ``players`` table is intentionally not a read fallback here: a
        # profile is the only reusable player record.
        async with db.execute(
            """SELECT p.* FROM tournament_player_links l
               INNER JOIN player_profiles p ON p.id = l.player_profile_id
                   AND p.workspace_id = l.workspace_id
               WHERE l.workspace_id = ? AND l.tournament_slug = ? AND l.entrant_id = ?""",
            (workspace_id, tournament_slug.strip(), str(entrant_id).strip()),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def sync_entrant_presentation_to_profile(
    workspace_id: str,
    tournament_slug: str,
    entrant_id: str,
    data: dict[str, Any],
    game_id: str | None,
) -> dict[str, Any] | None:
    """Make a linked entrant edit durable on its Player Archive profile.

    A participant can still have a tournament projection for rendering, but
    it must never become a competing player record. This helper is used by
    Participants & Overrides after catalog/scope validation has completed.
    """
    profile = await get_entrant_linked_profile(workspace_id, tournament_slug, entrant_id)
    if not profile:
        return None

    profile_updates: dict[str, Any] = {}
    if "name" in data or "display_name" in data:
        profile_updates["display_name"] = data.get("name", data.get("display_name"))
    for key in ("prefix", "country", "avatar_url"):
        if key in data:
            profile_updates[key] = data[key]
    if profile_updates:
        await update_player_profile(str(profile["id"]), workspace_id, profile_updates)

    clean_game_id = str(game_id or "").strip()
    if clean_game_id and (data.get("character_id") or data.get("cfn")):
        game_profile = await set_player_game_profile(
            workspace_id=workspace_id,
            player_profile_id=str(profile["id"]),
            game_id=clean_game_id,
            in_game_name=str(profile_updates.get("display_name") or profile.get("display_name") or "").strip() or None,
            in_game_id=str(data.get("cfn") or "").strip() or None,
        )
        if data.get("character_id"):
            await set_player_character_default(
                workspace_id=workspace_id,
                player_game_profile_id=str(game_profile["id"]),
                character_id=str(data["character_id"]),
                character_name=str(data.get("character") or data.get("character_name") or ""),
                character_image_url=str(data.get("character_image_url") or "") or None,
                is_primary=True,
            )
    return await get_player_profile(str(profile["id"]), workspace_id)
