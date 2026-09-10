"""PostgreSQL acceptance for tenant-owned reads and background claims."""
from __future__ import annotations

import asyncio
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

from backend.core import database


PG_TEST_URL = os.getenv("AITOB_PG_TEST_URL")
pytestmark = pytest.mark.skipif(not PG_TEST_URL, reason="requires explicit AITOB_PG_TEST_URL")


@pytest.fixture(autouse=True)
async def isolated_postgres(monkeypatch: pytest.MonkeyPatch):
    import psycopg
    from psycopg import sql

    parts = urlsplit(PG_TEST_URL or "")
    name = "aitob_scope_" + uuid.uuid4().hex
    admin = urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment))
    target = urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}" ).format(sql.Identifier(name)))
    monkeypatch.setenv("DATABASE_URL", target)
    try:
        await database.init_db()
        yield
    finally:
        with psycopg.connect(admin, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}" ).format(sql.Identifier(name)))


async def _workspace(db, workspace_id: str) -> None:
    await db.execute(
        "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
        (workspace_id, workspace_id, workspace_id),
    )


@pytest.mark.asyncio
async def test_tenant_player_projection_and_links_exclude_unowned_rows():
    async with database.aiosqlite.connect(database.DB_PATH) as db:
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
        async with database.aiosqlite.connect(database.DB_PATH) as db:
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
    async with database.aiosqlite.connect(database.DB_PATH) as db:
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
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        match = await (await db.execute("SELECT hub_status FROM active_matches WHERE set_id='match-shared'")).fetchone()
        count = await (await db.execute("SELECT COUNT(*) FROM workflow_outbox")).fetchone()
    assert match[0] is None
    assert count[0] == 0
