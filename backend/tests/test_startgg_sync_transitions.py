"""Tests for start.gg-mode sync-driven transitions (Dual-Mode Check-in, Commit 3).

When check_in_source='startgg', the reconciliation poll (sync_active_matches) must:
  • advance a `called` match to `in_progress` when start.gg goes ACTIVE, stamp started_at,
    and enqueue `startgg_go_live` exactly once (edge-triggered, not every tick);
  • close a match to `complete` when start.gg goes COMPLETED, free the station, and enqueue
    `startgg_finish <sid> <thread_id>` once;
  • leave 'discord'-mode matches completely unaffected (no auto-advance, no commands).
"""
import os
import pytest
import aiosqlite

from backend.core.database import (
    init_db, upsert_tournament, upsert_active_match, get_active_match,
    update_tournament_settings, sync_active_matches, get_pending_hub_commands,
)
from backend.core.contracts.tournament_types import (
    ProviderSet, ProviderSetState, ProviderEntrant,
)

TEST_DB_PATH = "backend/core/test_startgg_sync.sqlite"
SLUG = "tournament/dualsync"


@pytest.fixture
async def setup_test_db():
    import backend.core.database
    import backend.core.match_state

    orig = backend.core.database.DB_PATH
    backend.core.database.DB_PATH = TEST_DB_PATH
    backend.core.match_state.DB_PATH = TEST_DB_PATH
    await init_db()
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    backend.core.database.DB_PATH = orig
    backend.core.match_state.DB_PATH = orig


def _set(state, sid="s1"):
    return ProviderSet(
        id=sid, state=state, round_name="Winners Semi-Final", identifier="A",
        phase_group="1", event_id="ev1", event_name="SF6",
        entrant1=ProviderEntrant(id="11", name="Alice"),
        entrant2=ProviderEntrant(id="22", name="Bob"),
    )


async def _arm(check_in_source):
    await upsert_tournament(SLUG, "Dual Sync", "", "", "", "{}")
    await update_tournament_settings(SLUG, check_in_source=check_in_source)


async def _cmds():
    return [c["command_text"] for c in await get_pending_hub_commands()]


# ── called → in_progress (start.gg ACTIVE) ──────────────────────────────────
@pytest.mark.asyncio
async def test_startgg_called_to_in_progress_enqueues_go_live(setup_test_db):
    await _arm("startgg")
    await upsert_active_match(
        "s1", tournament_slug=SLUG, event_id="ev1", status="called",
        p1_name="Alice", p2_name="Bob", p1_entrant_id="11", p2_entrant_id="22",
        discord_thread_id="999",
    )

    await sync_active_matches(SLUG, [_set(ProviderSetState.IN_PROGRESS)])

    m = await get_active_match("s1")
    assert m["status"] == "in_progress"
    assert m["started_at"]  # stamped
    assert "startgg_go_live s1" in await _cmds()


@pytest.mark.asyncio
async def test_startgg_go_live_is_edge_triggered_not_repeated(setup_test_db):
    await _arm("startgg")
    await upsert_active_match(
        "s1", tournament_slug=SLUG, event_id="ev1", status="called",
        p1_name="Alice", p2_name="Bob", p1_entrant_id="11", p2_entrant_id="22",
        discord_thread_id="999",
    )
    # First tick: called -> in_progress, enqueues once.
    await sync_active_matches(SLUG, [_set(ProviderSetState.IN_PROGRESS)])
    # Second tick: already in_progress, provider still ACTIVE — must NOT re-enqueue.
    await sync_active_matches(SLUG, [_set(ProviderSetState.IN_PROGRESS)])

    assert (await _cmds()).count("startgg_go_live s1") == 1


# ── * → complete (start.gg COMPLETED / auto-double-DQ / self-report) ─────────
@pytest.mark.asyncio
async def test_startgg_complete_frees_station_and_enqueues_finish(setup_test_db):
    await _arm("startgg")
    await upsert_active_match(
        "s1", tournament_slug=SLUG, event_id="ev1", status="in_progress",
        p1_name="Alice", p2_name="Bob", p1_entrant_id="11", p2_entrant_id="22",
        discord_thread_id="999", is_stream_match=1, station_id="station_1",
    )

    await sync_active_matches(SLUG, [_set(ProviderSetState.COMPLETE)])

    m = await get_active_match("s1")
    assert m["status"] == "complete"
    assert not m["station_id"]  # freed
    assert "startgg_finish s1 999" in await _cmds()


# ── discord mode is unaffected ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_discord_mode_does_not_auto_advance_or_enqueue(setup_test_db):
    await _arm("discord")
    await upsert_active_match(
        "s1", tournament_slug=SLUG, event_id="ev1", status="called",
        p1_name="Alice", p2_name="Bob", p1_entrant_id="11", p2_entrant_id="22",
        discord_thread_id="999",
    )

    await sync_active_matches(SLUG, [_set(ProviderSetState.IN_PROGRESS)])

    m = await get_active_match("s1")
    assert m["status"] == "called"  # bot button flow owns this, not the poll
    cmds = await _cmds()
    assert not any(c.startswith("startgg_") for c in cmds)
