import pytest
from backend.core import database
from backend.core.tournament_setup import create_draft, patch_draft
from backend.core.tournament_activation import ActivationError, materialize_draft, activate_tournament


@pytest.mark.asyncio
async def test_materialize_and_activate_are_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "activation.pg"))
    await database.init_db()
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces(id,slug,name) VALUES ('w','w','W')")
        await db.execute("INSERT INTO users(id,email,display_name,password_hash) VALUES ('u','u@example.com','U','x')")
        await db.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name)
               VALUES ('a', 'w', 'w', 'startgg', 'remote-a', 'Start.gg')"""
        )
        await db.commit()
    draft = await create_draft("w", "u")
    draft = await patch_draft(draft["id"], "w", "u", section="provider_scope", value={"provider": "startgg", "account_id": "a", "selected_scope": {"external_id": "e", "name": "E"}, "tournament": {"external_id": "t", "canonical_slug": "t", "name": "T"}}, expected_revision=draft["revision"], current_step="provider")
    draft = await patch_draft(draft["id"], "w", "u", section="tournament_review", value={"display_name": "T"}, expected_revision=draft["revision"], current_step="tournament")
    materialized = await materialize_draft(draft["id"], "w", "u", expected_revision=draft["revision"])
    active = await activate_tournament("w", materialized["tournament_id"], "u", idempotency_key="x")
    replay = await activate_tournament("w", materialized["tournament_id"], "u", idempotency_key="x")
    assert active["status"] == replay["status"] == "active"
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        count = await (await db.execute("SELECT COUNT(*) FROM workflow_outbox WHERE event_type='initial_sync'")).fetchone()
    assert count[0] == 1


@pytest.mark.asyncio
async def test_materialization_resolves_discord_channel_to_destination_id(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "discord-activation.pg"))
    await database.init_db()
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces(id,slug,name) VALUES ('w','w','W')")
        await db.execute("INSERT INTO users(id,email,display_name,password_hash) VALUES ('u','u@example.com','U','x')")
        await db.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name, metadata_json)
               VALUES
               ('provider-a', 'w', 'w', 'startgg', 'remote-a', 'Start.gg', '{}'),
               ('discord-a', 'w', 'w', 'discord', 'guild-1', 'Discord', '{"installation_verified":true}')"""
        )
        await db.execute(
            """INSERT INTO integration_destinations
               (id, account_id, workspace_id, destination_type, external_id, display_name)
               VALUES ('destination-1', 'discord-a', 'w', 'match_call_channel', 'channel-1', 'Matches')"""
        )
        await db.commit()

    draft = await create_draft("w", "u")
    draft = await patch_draft(
        draft["id"], "w", "u", section="provider_scope",
        value={
            "provider": "startgg", "account_id": "provider-a",
            "selected_scope": {"external_id": "event-1", "name": "Event"},
            "tournament": {"external_id": "tournament-1", "canonical_slug": "discord-test", "name": "Discord Test"},
        },
        expected_revision=draft["revision"], current_step="provider",
    )
    draft = await patch_draft(
        draft["id"], "w", "u", section="tournament_review",
        value={"display_name": "Discord Test"},
        expected_revision=draft["revision"], current_step="tournament",
    )
    draft = await patch_draft(
        draft["id"], "w", "u", section="discord_setup",
        value={
            "enabled": True, "discord_account_id": "discord-a",
            "guild_id": "guild-1", "destination_external_id": "channel-1",
        },
        expected_revision=draft["revision"], current_step="discord",
    )

    materialized = await materialize_draft(
        draft["id"], "w", "u", expected_revision=draft["revision"]
    )
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        row = await (await db.execute(
            """SELECT b.match_destination_id, b.escalation_destination_id, d.external_id
                 FROM tournament_discord_bindings b
                 JOIN integration_destinations d ON d.id=b.match_destination_id
                WHERE b.tournament_id=?""",
            (materialized["tournament_id"],),
        )).fetchone()

    assert row is not None
    assert row[0] == row[1]
    assert row[2] == "channel-1"


@pytest.mark.asyncio
async def test_materialization_rejects_unverified_discord_installation_and_channel(
    postgres_repository_database,
):
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces(id,slug,name) VALUES ('w','w','W')")
        await db.execute("INSERT INTO users(id,email,display_name,password_hash) VALUES ('u','u@example.com','U','x')")
        await db.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name, metadata_json)
               VALUES
               ('provider-a', 'w', 'w', 'startgg', 'remote-a', 'Start.gg', '{}'),
               ('discord-a', 'w', 'w', 'discord', 'guild-1', 'Discord', '{"installation_verified":true}')"""
        )
        await db.commit()

    draft = await create_draft("w", "u")
    draft = await patch_draft(
        draft["id"], "w", "u", section="provider_scope",
        value={
            "provider": "startgg", "account_id": "provider-a",
            "selected_scope": {"external_id": "event-1", "name": "Event"},
            "tournament": {"external_id": "tournament-1", "canonical_slug": "discord-unverified", "name": "Discord Test"},
        },
        expected_revision=draft["revision"], current_step="provider",
    )
    draft = await patch_draft(
        draft["id"], "w", "u", section="discord_setup",
        value={
            "enabled": True, "discord_account_id": "discord-a",
            "guild_id": "guild-1", "destination_external_id": "never-verified",
        },
        expected_revision=draft["revision"], current_step="discord",
    )

    with pytest.raises(ActivationError, match="permission check"):
        await materialize_draft(draft["id"], "w", "u", expected_revision=draft["revision"])
