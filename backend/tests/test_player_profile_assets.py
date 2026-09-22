"""Asset-preservation and old-URL/reference regression tests for player profiles."""

from __future__ import annotations
import json
from unittest.mock import AsyncMock

import pytest

from backend.core import database
from backend.core import player_profiles
from backend.core.player_presentation import (
    EntrantScope,
    resolve_presentation_v1,
    resolve_entrant_presentation,
    PLACEHOLDER_AVATAR,
)


@pytest.mark.asyncio
async def test_avatar_asset_preserved_during_backfill_and_profile_sync(postgres_repository_database):
    """Verify that existing avatar paths and media_assets records are preserved

    when creating/migrating player profiles.
    """
    workspace_id = "ws-asset-preservation"
    discord_id = "user-asset-1"
    avatar_url = "/static/avatars/user_asset_1_durable.png"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
            (workspace_id, "asset-ws", "Asset WS"),
        )
        # Seed an asset in media_assets ledger
        await db.execute(
            """INSERT INTO media_assets (id, workspace_id, asset_type, owner_type, owner_id, storage_url, storage_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("asset-uuid-1", workspace_id, "avatar", "player", discord_id, avatar_url, "avatars/asset1.png"),
        )
        await db.commit()

    # Create player in legacy table with this avatar
    await database.create_or_update_player(
        discord_id=discord_id,
        workspace_id=workspace_id,
        gamer_tag="AssetGamer",
        avatar_path=avatar_url,
    )

    # Run the backfill / migration sync
    await database.backfill_player_profiles_and_overrides(workspace_id=workspace_id)

    # Verify player_profiles row received the exact avatar_url
    prof = await player_profiles.get_player_profile_by_discord_id(discord_id, workspace_id)
    assert prof is not None
    assert prof["avatar_url"] == avatar_url
    assert prof["display_name"] == "AssetGamer"

    # Verify media_assets entry is still active (not deleted)
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        async with db.execute(
            "SELECT storage_url, deleted_at FROM media_assets WHERE id = ?",
            ("asset-uuid-1",),
        ) as cur:
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == avatar_url
            assert row[1] is None  # deleted_at is null


@pytest.mark.asyncio
async def test_avatar_fallback_resilience_when_missing_or_null(postgres_repository_database):
    """Verify that when a profile avatar is missing or null,

    the resolver safely falls back to provider image, or placeholder without errors.
    """
    scope = EntrantScope(
        provider="startgg",
        tournament_slug="tourney",
        event_id="ev1",
        entrant_id="ent1",
    )

    # Case 1: Profile has null avatar, Provider has avatar -> Provider avatar used
    res1 = resolve_presentation_v1(
        scope,
        profile={"id": "p1", "display_name": "Pro 1", "avatar_url": None},
        provider_snapshot={"name": "P1", "avatar_url": "https://cdn.example/provider_img.png"},
        linked=True,
    )
    assert res1.presentation.avatar_url.value == "https://cdn.example/provider_img.png"
    assert res1.presentation.avatar_url.source == "provider_snapshot"

    # Case 2: Profile has empty avatar, Provider has no avatar -> Placeholder used
    res2 = resolve_presentation_v1(
        scope,
        profile={"id": "p1", "display_name": "Pro 1", "avatar_url": "   "},
        provider_snapshot={"name": "P1"},
        linked=True,
    )
    assert res2.presentation.avatar_url.value == PLACEHOLDER_AVATAR
    assert res2.presentation.avatar_url.source == "placeholder"

    # Case 3: Profile has valid avatar -> Profile avatar used with profile provenance
    res3 = resolve_presentation_v1(
        scope,
        profile={"id": "p1", "display_name": "Pro 1", "avatar_url": "/static/avatars/valid.png"},
        provider_snapshot={"avatar_url": "https://cdn.example/provider.png"},
        linked=True,
    )
    assert res3.presentation.avatar_url.value == "/static/avatars/valid.png"
    assert res3.presentation.avatar_url.source == "player_profile"


@pytest.mark.asyncio
async def test_retire_media_assets_scoped_to_workspace_and_player(postgres_repository_database):
    """Verify asset retirement ledger updates do not affect other workspaces or players."""
    ws_1 = "ws-asset-iso-1"
    ws_2 = "ws-asset-iso-2"
    url_1 = "/static/avatars/user1_old.png"
    url_2 = "/static/avatars/user2_keep.png"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (ws_1, "ws-1", "WS 1"))
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (ws_2, "ws-2", "WS 2"))
        # ws-1 asset
        await db.execute(
            """INSERT INTO media_assets (id, workspace_id, asset_type, owner_type, owner_id, storage_url, storage_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("m-1", ws_1, "avatar", "player", "u-1", url_1, "key1"),
        )
        # ws-2 asset with same URL pattern
        await db.execute(
            """INSERT INTO media_assets (id, workspace_id, asset_type, owner_type, owner_id, storage_url, storage_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("m-2", ws_2, "avatar", "player", "u-2", url_2, "key2"),
        )
        await db.commit()

    # Retire url_1 in ws_1
    await database.retire_media_assets_for_urls([url_1], workspace_id=ws_1)

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        # m-1 should have deleted_at set
        async with db.execute("SELECT deleted_at FROM media_assets WHERE id = 'm-1'") as cur:
            row1 = await cur.fetchone()
            assert row1[0] is not None

        # m-2 should be untouched
        async with db.execute("SELECT deleted_at FROM media_assets WHERE id = 'm-2'") as cur:
            row2 = await cur.fetchone()
            assert row2[0] is None


@pytest.mark.asyncio
async def test_media_asset_cannot_be_deleted_while_profile_or_scoped_override_references_it(postgres_repository_database):
    """Profile-domain avatar references are as durable as legacy player references."""
    workspace_id = "ws-asset-reference-profile"
    avatar_url = "/static/avatars/profile_reference.png"
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (workspace_id, "asset-ref", "Asset Ref"))
        await db.execute(
            """INSERT INTO media_assets (id, workspace_id, asset_type, storage_url, storage_key)
               VALUES (?, ?, ?, ?, ?)""",
            ("profile-reference-asset", workspace_id, "participant_avatar", avatar_url, "profile_reference.png"),
        )
        await db.commit()

    profile = await player_profiles.create_player_profile(workspace_id, "Asset Profile", avatar_url=avatar_url)
    with pytest.raises(ValueError, match="still referenced"):
        await database.delete_media_asset("profile-reference-asset", workspace_id)

    await player_profiles.update_player_profile(profile["id"], workspace_id, {"avatar_url": None})
    await player_profiles.set_tournament_entrant_override(
        workspace_id, "startgg", "asset-tourney", "asset-event", "asset-entrant",
        {"avatar_url": avatar_url},
    )
    with pytest.raises(ValueError, match="still referenced"):
        await database.delete_media_asset("profile-reference-asset", workspace_id)
