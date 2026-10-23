"""PostgreSQL repository tests for Tournament Results Media."""

from __future__ import annotations

import asyncio
import uuid
import pytest
from backend.core import database
from backend.core import results_media_repository as repo


async def _seed_workspace_and_user(db, ws_id: str, user_id: str):
    await db.execute(
        "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
        (ws_id, f"slug-{ws_id}", f"Workspace {ws_id}"),
    )
    await db.execute(
        "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
        (user_id, f"{user_id}@example.com", f"User {user_id}", "hash"),
    )
    await db.commit()


@pytest.mark.asyncio
async def test_result_version_creation_and_hash_reuse(postgres_repository_database):
    """Verify result version and entries are persisted atomically and deduplicated by hash."""
    ws_id = "ws-repo-test-1"
    user_id = "usr-repo-1"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await _seed_workspace_and_user(db, ws_id, user_id)

    obs_hash = "hash-1234567890abcdef"
    v_id = str(uuid.uuid4())
    version_data = {
        "id": v_id,
        "workspace_id": ws_id,
        "tournament_slug": "smash-weekly-1",
        "provider_type": "startgg",
        "provider_account_id": "acc-1",
        "provider_tournament_id": "tourney-1",
        "event_id": "event-1",
        "event_name": "Smash Ultimate Singles",
        "game_id": "game-smash",
        "game_name": "Super Smash Bros. Ultimate",
        "capture_status": "final",
        "provider_state_raw": "COMPLETED",
        "provider_revision": "rev-1",
        "provider_payload_hash": "payload-hash",
        "presentation_hash": "pres-hash",
        "observation_hash": obs_hash,
        "observed_at": "2026-09-28T12:00:00Z",
        "finalized_at": "2026-09-28T12:00:00Z",
        "warning_json": [],
        "event_metadata_json": {"title": "Smash Weekly 1"},
        "entry_count": 2,
        "created_by": user_id,
    }

    entries = [
        {
            "ordinal": 1,
            "placement": 1,
            "entrant_id": "ent-1",
            "entrant_name": "Champion Player",
            "is_tied": False,
            "presentation_json": {"display_name": {"value": "Champion Player", "source": "provider_snapshot"}},
        },
        {
            "ordinal": 2,
            "placement": 2,
            "entrant_id": "ent-2",
            "entrant_name": "Runner Up",
            "is_tied": False,
            "presentation_json": {"display_name": {"value": "Runner Up", "source": "provider_snapshot"}},
        },
    ]

    created = await repo.create_result_version_with_entries(ws_id, version_data, entries)
    assert created["id"] == v_id
    assert created["entry_count"] == 2

    # Check hash lookup finds existing version
    existing = await repo.get_result_version_by_hash(ws_id, "smash-weekly-1", "event-1", obs_hash)
    assert existing is not None
    assert existing["id"] == v_id

    # Check latest version lookup
    latest = await repo.get_latest_result_version(ws_id, "smash-weekly-1", "event-1")
    assert latest is not None
    assert latest["id"] == v_id


@pytest.mark.asyncio
async def test_concurrent_identical_result_version_creation_is_atomic(
    postgres_repository_database,
):
    ws_id = "ws-repo-concurrent"
    user_id = "usr-repo-concurrent"
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await _seed_workspace_and_user(db, ws_id, user_id)

    version_data = {
        "tournament_slug": "concurrent-cup",
        "provider_type": "startgg",
        "provider_account_id": "acc-concurrent",
        "provider_tournament_id": "provider-concurrent",
        "event_id": "event-concurrent",
        "event_name": "Concurrent Event",
        "capture_status": "final",
        "provider_state_raw": "COMPLETED",
        "provider_payload_hash": "payload-concurrent",
        "presentation_hash": "presentation-concurrent",
        "observation_hash": "observation-concurrent",
        "observed_at": "2026-09-28T12:00:00Z",
        "created_by": user_id,
    }
    entries = [{
        "ordinal": 1,
        "placement": 1,
        "entrant_id": "winner-concurrent",
        "entrant_name": "Concurrent Winner",
        "is_tied": False,
        "presentation_json": {},
    }]

    created = await asyncio.gather(*[
        repo.create_result_version_with_entries(
            ws_id,
            {**version_data, "id": str(uuid.uuid4())},
            entries,
        )
        for _ in range(2)
    ])

    assert created[0]["id"] == created[1]["id"]
    assert sorted(item["_created"] for item in created) == [False, True]
    stored_entries, _ = await repo.get_version_entries(ws_id, created[0]["id"])
    assert [item["entrant_id"] for item in stored_entries] == ["winner-concurrent"]


@pytest.mark.asyncio
async def test_top_n_ties_and_ordering(postgres_repository_database):
    """Verify Top 8 includes all entrants with placement <= 8, preserving ties and order."""
    ws_id = "ws-ties-test"
    user_id = "usr-ties"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await _seed_workspace_and_user(db, ws_id, user_id)

    v_id = str(uuid.uuid4())
    # 9 entrants: 1st, 2nd, 3rd, 4th, 5th, 5th, 7th, 7th, 7th (3-way tie for 7th -> 9 entrants in Top 8)
    placements = [1, 2, 3, 4, 5, 5, 7, 7, 7, 9, 10]
    entries = []
    for i, p in enumerate(placements, 1):
        entries.append({
            "ordinal": i,
            "placement": p,
            "entrant_id": f"ent-{i}",
            "entrant_name": f"Player {i}",
            "is_tied": placements.count(p) > 1,
            "presentation_json": {"display_name": {"value": f"Player {i}", "source": "provider_snapshot"}},
        })

    version_data = {
        "id": v_id,
        "workspace_id": ws_id,
        "tournament_slug": "sf6-monthly",
        "provider_type": "challonge",
        "provider_account_id": "acc-ch",
        "provider_tournament_id": "tourney-ch",
        "event_id": "tourney-ch",
        "event_name": "Street Fighter 6",
        "capture_status": "final",
        "provider_state_raw": "complete",
        "provider_payload_hash": "ph",
        "presentation_hash": "prh",
        "observation_hash": "obs-ties",
        "observed_at": "2026-09-28T12:00:00Z",
        "entry_count": len(entries),
        "created_by": user_id,
    }

    await repo.create_result_version_with_entries(ws_id, version_data, entries)

    # Query Top 8
    top8_entries, page = await repo.get_version_entries(ws_id, v_id, cutoff="top8", page=1, page_size=16)
    # Entrants with placement <= 8 are 9 entrants
    assert len(top8_entries) == 9
    assert all(e["placement"] <= 8 for e in top8_entries)

    # Check ordering is placement ASC then ordinal ASC
    for i in range(len(top8_entries) - 1):
        curr = top8_entries[i]
        nxt = top8_entries[i + 1]
        assert (curr["placement"], curr["ordinal"]) < (nxt["placement"], nxt["ordinal"])

    all_page_2, page_2 = await repo.get_version_entries(
        ws_id, v_id, cutoff="all", page=2, page_size=4
    )
    assert [entry["ordinal"] for entry in all_page_2] == [5, 6, 7, 8]
    assert page_2 == {"number": 2, "size": 4, "total_entries": 11, "has_more": True}


@pytest.mark.asyncio
async def test_workspace_isolation_denies_cross_tenant_reads(postgres_repository_database):
    """Verify workspace B cannot read workspace A result version or entries."""
    ws_a = "ws-iso-a"
    ws_b = "ws-iso-b"
    usr_a = "usr-iso-a"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await _seed_workspace_and_user(db, ws_a, usr_a)
        await _seed_workspace_and_user(db, ws_b, "usr-iso-b")

    v_id = str(uuid.uuid4())
    version_data = {
        "id": v_id,
        "workspace_id": ws_a,
        "tournament_slug": "t-a",
        "provider_type": "startgg",
        "provider_account_id": "acc-a",
        "provider_tournament_id": "ta",
        "event_id": "ev-a",
        "event_name": "Event A",
        "capture_status": "final",
        "provider_state_raw": "COMPLETED",
        "provider_payload_hash": "pa",
        "presentation_hash": "pra",
        "observation_hash": "obsa",
        "observed_at": "2026-09-28T12:00:00Z",
        "entry_count": 1,
        "created_by": usr_a,
    }
    entries = [{
        "ordinal": 1,
        "placement": 1,
        "entrant_id": "e-1",
        "entrant_name": "Winner A",
        "is_tied": False,
        "presentation_json": {},
    }]

    await repo.create_result_version_with_entries(ws_a, version_data, entries)

    # Workspace A can read
    assert (await repo.get_result_version_by_id(ws_a, v_id)) is not None

    # Workspace B reading version by ID returns None
    assert (await repo.get_result_version_by_id(ws_b, v_id)) is None

    # Workspace B reading entries returns empty
    entries_b, _ = await repo.get_version_entries(ws_b, v_id)
    assert len(entries_b) == 0


@pytest.mark.asyncio
async def test_media_output_and_export_receipt(postgres_repository_database):
    """Verify creating media output and recording client export receipt."""
    ws_id = "ws-out-test"
    user_id = "usr-out"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await _seed_workspace_and_user(db, ws_id, user_id)

    v_id = str(uuid.uuid4())
    await repo.create_result_version_with_entries(
        ws_id,
        {
            "id": v_id,
            "workspace_id": ws_id,
            "tournament_slug": "t-slug",
            "provider_type": "startgg",
            "provider_account_id": "acc-1",
            "provider_tournament_id": "t-1",
            "event_id": "ev-1",
            "event_name": "Event 1",
            "capture_status": "final",
            "provider_state_raw": "COMPLETED",
            "provider_payload_hash": "p",
            "presentation_hash": "pr",
            "observation_hash": "ob",
            "observed_at": "2026-09-28T12:00:00Z",
            "entry_count": 1,
            "created_by": user_id,
        },
        [{"ordinal": 1, "placement": 1, "entrant_id": "e1", "entrant_name": "P1", "is_tied": False, "presentation_json": {}}],
    )

    out_id = str(uuid.uuid4())
    output_data = {
        "id": out_id,
        "workspace_id": ws_id,
        "result_version_id": v_id,
        "output_kind": "static",
        "overlay_name": "Top 8 Social",
        "scene_schema_version": 2,
        "scene_config_json": {"schemaVersion": 2, "dataSource": {"kind": "tournament-results"}},
        "scene_hash": "scene-hash-abc",
        "cutoff": "top8",
        "page_number": 1,
        "output_profile_json": {"width": 1920, "height": 1080},
        "created_by": user_id,
    }

    out = await repo.create_media_output(ws_id, output_data)
    assert out["id"] == out_id

    # Record receipt
    digest = "a" * 64
    status = await repo.record_export_receipt(ws_id, out_id, byte_size=102400, sha256=digest)
    assert status == "recorded"

    # The receipt is immutable but an exact retry remains idempotent.
    assert await repo.record_export_receipt(
        ws_id, out_id, byte_size=102400, sha256=digest
    ) == "unchanged"
    assert await repo.record_export_receipt(
        ws_id, out_id, byte_size=102401, sha256="b" * 64
    ) == "conflict"

    fetched = await repo.get_media_output(ws_id, out_id)
    assert fetched is not None
    assert fetched["export_byte_size"] == 102400
    assert fetched["export_sha256"] == digest
