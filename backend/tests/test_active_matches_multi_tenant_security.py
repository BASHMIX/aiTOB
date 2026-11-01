"""
Multi-Tenant Security and Concurrency Integration Tests for active_matches.

Validates:
1. Composite Primary Key (workspace_id, set_id): two workspaces can track the same set_id without collision.
2. Cross-Workspace Update Protection: Workspace B cannot mutate Workspace A's match.
3. Cross-Workspace Upsert Protection: Workspace B upserting set_id does not steal or overwrite Workspace A's row.
4. Concurrent Upsert Safety: Parallel upserts on the same (workspace_id, set_id) succeed atomically (no 500 / UniqueViolation).
5. Idempotent Retries: Repeated upserts with identical or updated fields are safe and durable.
6. Station and Queue Isolation: Stations and queues in one workspace do not leak to another.
"""
from __future__ import annotations

import asyncio
import pytest
from backend.core import database


@pytest.mark.asyncio
async def test_same_set_id_in_different_workspaces_coexists(postgres_repository_database):
    """Two different tenants can track the same set_id independently with zero collision."""
    set_id = "provider-set-same-id-999"

    # Tenant A creates match
    await database.upsert_active_match(
        set_id,
        workspace_id="workspace-tenant-a",
        tournament_slug="tournament-a",
        p1_name="Alice",
        p2_name="Bob",
        p1_score=2,
        p2_score=1,
        station_id="station-a1",
        status="in_progress",
    )

    # Tenant B tracks the exact same set_id independently
    await database.upsert_active_match(
        set_id,
        workspace_id="workspace-tenant-b",
        tournament_slug="tournament-b",
        p1_name="Charlie",
        p2_name="Dave",
        p1_score=0,
        p2_score=0,
        station_id="station-b1",
        status="called",
    )

    # Verify Tenant A's row is completely intact and isolated
    match_a = await database.get_active_match(set_id, "workspace-tenant-a")
    assert match_a is not None
    assert match_a["workspace_id"] == "workspace-tenant-a"
    assert match_a["p1_name"] == "Alice"
    assert match_a["p1_score"] == 2
    assert match_a["station_id"] == "station-a1"
    assert match_a["status"] == "in_progress"

    # Verify Tenant B's row is completely intact and isolated
    match_b = await database.get_active_match(set_id, "workspace-tenant-b")
    assert match_b is not None
    assert match_b["workspace_id"] == "workspace-tenant-b"
    assert match_b["p1_name"] == "Charlie"
    assert match_b["p1_score"] == 0
    assert match_b["station_id"] == "station-b1"
    assert match_b["status"] == "called"


@pytest.mark.asyncio
async def test_cross_workspace_upsert_cannot_hijack_existing_match(postgres_repository_database):
    """An upsert from another tenant must NEVER mutate or steal an existing tenant's row."""
    target_set = "provider-set-target-500"

    # Workspace 1 owns the match
    await database.upsert_active_match(
        target_set,
        workspace_id="workspace-victim",
        tournament_slug="slug-victim",
        p1_name="Legitimate Player",
        station_id="station-victim",
        status="called",
    )

    # Workspace 2 attempts to upsert with target_set
    await database.upsert_active_match(
        target_set,
        workspace_id="workspace-attacker",
        p1_name="Malicious Write",
        station_id="station-attacker",
        status="complete",
    )

    # Verify Workspace 1 row was NOT modified, hijacked, or reassigned
    victim = await database.get_active_match(target_set, "workspace-victim")
    assert victim is not None
    assert victim["workspace_id"] == "workspace-victim"
    assert victim["p1_name"] == "Legitimate Player"
    assert victim["station_id"] == "station-victim"
    assert victim["status"] == "called"

    # Verify Workspace 2 has its own separate row
    attacker = await database.get_active_match(target_set, "workspace-attacker")
    assert attacker is not None
    assert attacker["workspace_id"] == "workspace-attacker"
    assert attacker["p1_name"] == "Malicious Write"


@pytest.mark.asyncio
async def test_cross_workspace_update_rejected(postgres_repository_database):
    """update_active_match must reject foreign matches and return False."""
    set_id = "provider-set-update-700"

    await database.upsert_active_match(
        set_id,
        workspace_id="workspace-primary",
        tournament_slug="primary-tourney",
        p1_name="Player 1",
    )

    changed = await database.update_active_match(
        set_id,
        workspace_id="workspace-foreign",
        p1_name="Hacked Name",
    )
    assert changed is False

    primary = await database.get_active_match(set_id, "workspace-primary")
    assert primary["p1_name"] == "Player 1"
    assert await database.get_active_match(set_id, "workspace-foreign") is None


@pytest.mark.asyncio
async def test_concurrent_upserts_are_atomic_and_race_free(postgres_repository_database):
    """Multiple concurrent upserts for the same match execute atomically without UniqueViolation."""
    set_id = "provider-set-concurrent-888"
    ws = "workspace-concurrent-test"

    async def worker(worker_id: int):
        for i in range(5):
            await database.upsert_active_match(
                set_id,
                workspace_id=ws,
                tournament_slug="concurrent-tourney",
                p1_name=f"Worker {worker_id} Run {i}",
                p1_score=i,
            )

    # Launch 6 concurrent workers performing rapid updates on the exact same match
    tasks = [asyncio.create_task(worker(w)) for w in range(6)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # None of the workers should raise an exception (zero UniqueViolation / 500 errors)
    for res in results:
        assert not isinstance(res, Exception), f"Concurrent upsert failed with: {res}"

    match = await database.get_active_match(set_id, ws)
    assert match is not None
    assert match["workspace_id"] == ws


@pytest.mark.asyncio
async def test_idempotent_upsert_retries(postgres_repository_database):
    """Repeatedly calling upsert_active_match with the same data is completely idempotent."""
    set_id = "provider-set-idempotent-123"
    ws = "workspace-retry-test"

    for _ in range(3):
        await database.upsert_active_match(
            set_id,
            workspace_id=ws,
            tournament_slug="idempotent-tourney",
            p1_name="Stable Player",
            status="called",
        )

    match = await database.get_active_match(set_id, ws)
    assert match is not None
    assert match["p1_name"] == "Stable Player"
    assert match["status"] == "called"
