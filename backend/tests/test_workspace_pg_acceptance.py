"""PostgreSQL acceptance for tenant-owned reads and background claims."""
from __future__ import annotations

import asyncio
import pytest

from backend.core import database


async def _workspace(db, workspace_id: str) -> None:
    await db.execute(
        "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
        (workspace_id, workspace_id, workspace_id),
    )


@pytest.mark.asyncio
async def test_tenant_player_projection_and_links_exclude_unowned_rows():
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await _workspace(db, "scope-a")
        await _workspace(db, "scope-b")
        await db.execute("INSERT INTO players (discord_id, gamer_tag, workspace_id) VALUES ('p-a', 'A', 'scope-a')")
        await db.execute("INSERT INTO tournaments (slug, name, workspace_id) VALUES ('owned-a', 'A', 'scope-a')")
        await db.execute("INSERT INTO tournaments (slug, name) VALUES ('unowned', 'Legacy')")
        await db.execute(
            "INSERT INTO tournament_player_links (tournament_slug, entrant_id, player_discord_id, workspace_id) VALUES ('unowned', 'e-a', 'p-a', 'scope-a')"
        )
        await db.commit()

    assert [row["discord_id"] for row in await database.list_players_for_workspace("scope-a")] == ["p-a"]
    assert await database.list_players_for_workspace("scope-b") == []
    assert await database.get_tournament_player_links("unowned", "scope-a") == {}


@pytest.mark.asyncio
async def test_workspace_bound_workers_claim_only_their_provider_and_outbox_rows():
    for workspace in ("scope-a", "scope-b"):
        async with database.dbapi.connect(database.DATABASE_DSN) as db:
            await _workspace(db, workspace)
            await db.commit()
    base = {
        "tournament_slug": "scope/tournament", "set_id": "scope-match",
        "provider_type": "challonge", "provider_account_id": "scope-account",
        "action": "score", "idempotency_key": "scope-key", "payload_digest": "digest",
    }
    await database.create_provider_command_v2({**base, "id": "command-a", "workspace_id": "scope-a"})
    await database.create_provider_command_v2({**base, "id": "command-b", "workspace_id": "scope-b", "idempotency_key": "scope-key-b"})
    await database.enqueue_workflow_outbox_v2({
        "event_id": "event-a", "match_id": "scope-match", "event_type": "discord_call",
        "deduplication_key": "event-key-a", "workspace_id": "scope-a", "payload": {},
    })
    await database.enqueue_workflow_outbox_v2({
        "event_id": "event-b", "match_id": "scope-match", "event_type": "discord_call",
        "deduplication_key": "event-key-b", "workspace_id": "scope-b", "payload": {},
    })
    provider_a, provider_b = await asyncio.gather(
        database.claim_due_provider_commands_v2("2099-01-01T00:00:00Z", "2099-01-01T00:05:00Z", lease_owner="a", workspace_id="scope-a"),
        database.claim_due_provider_commands_v2("2099-01-01T00:00:00Z", "2099-01-01T00:05:00Z", lease_owner="b", workspace_id="scope-b"),
    )
    outbox_a, outbox_b = await asyncio.gather(
        database.claim_due_workflow_outbox_v2("2099-01-01T00:00:00Z", "2099-01-01T00:05:00Z", lease_owner="a", workspace_id="scope-a"),
        database.claim_due_workflow_outbox_v2("2099-01-01T00:00:00Z", "2099-01-01T00:05:00Z", lease_owner="b", workspace_id="scope-b"),
    )
    assert [row["workspace_id"] for row in provider_a] == ["scope-a"]
    assert [row["workspace_id"] for row in provider_b] == ["scope-b"]
    assert [row["workspace_id"] for row in outbox_a] == ["scope-a"]
    assert [row["workspace_id"] for row in outbox_b] == ["scope-b"]


@pytest.mark.asyncio
async def test_workspace_bound_workflow_cannot_mutate_foreign_match():
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await _workspace(db, "scope-a")
        await _workspace(db, "scope-b")
        await db.execute("INSERT INTO active_matches (set_id, workspace_id, status) VALUES ('match-shared', 'scope-a', 'not_started')")
        await db.commit()

    with pytest.raises(ValueError, match="Unknown match"):
        await database.update_hub_workflow_and_enqueue_outbox_v2(
            "match-shared", "called",
            {"event_id": "foreign-event", "event_type": "discord_call", "deduplication_key": "foreign-key"},
            workspace_id="scope-b",
        )
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        match = await (await db.execute("SELECT hub_status FROM active_matches WHERE set_id='match-shared'")).fetchone()
        count = await (await db.execute("SELECT COUNT(*) FROM workflow_outbox")).fetchone()
    assert match[0] is None
    assert count[0] == 0


@pytest.mark.asyncio
async def test_operational_workspace_ownership_gate_fails_closed_then_enforces():
    from backend.core.schema_migrations import POSTGRES_WORKSPACE_TABLES, enforce_postgres_workspace_ownership

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO tournaments (slug, name) VALUES ('unowned-gate', 'Legacy')")
        await db.commit()
        with pytest.raises(RuntimeError, match="backfill required"):
            await enforce_postgres_workspace_ownership(db)
        await db.execute("DELETE FROM tournaments WHERE slug='unowned-gate'")
        for table in POSTGRES_WORKSPACE_TABLES:
            await db.execute(f"UPDATE {table} SET workspace_id='scope-a' WHERE workspace_id IS NULL")
        await db.commit()
        await enforce_postgres_workspace_ownership(db)
        await db.commit()
        row = await (await db.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='tournaments' AND column_name='workspace_id'"
        )).fetchone()
    assert row[0] == "NO"
