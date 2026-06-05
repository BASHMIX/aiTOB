"""Tests for Option-A per-event auto-dispatch scoping + green-room stream routing.

Covers commit #7: a multi-game tournament (e.g. Tekken 8 + SF6 under one slug)
must dispatch each event as its own independent queue — concurrency, Top-N
threshold, and candidate selection are all scoped by event_id — and stream
matches must only land on an idle stream station bound to the same event.
"""
import os
import pytest

import aiosqlite

from backend.core.database import (
    init_db, upsert_active_match, upsert_tournament,
    get_dispatch_eligible_events, count_active_dispatched,
    count_remaining_event_matches, get_dispatch_candidates,
    get_available_stream_station, create_station, update_station,
    resolve_dispatch_budget,
)

TEST_DB_PATH = "backend/core/test_dispatch_event_scoping.sqlite"

EVENT_T8 = "100"
EVENT_SF6 = "200"
SLUG = "major/x"


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


async def _arm_tournament(slug=SLUG, concurrency=1, stop_at=2):
    await upsert_tournament(slug, "Major X", "", "", "", "{}")
    async with aiosqlite.connect(TEST_DB_PATH) as db:
        await db.execute(
            "UPDATE tournaments SET auto_dispatch_enabled = 1, "
            "auto_dispatch_concurrency = ?, auto_dispatch_stop_at = ? WHERE slug = ?",
            (concurrency, stop_at, slug),
        )
        await db.commit()


async def _seed_candidate(set_id, event_id, event_name, status="not_started", **extra):
    await upsert_active_match(
        set_id,
        tournament_slug=SLUG,
        event_id=event_id,
        event_name=event_name,
        p1_name="A", p2_name="B",
        p1_entrant_id="1", p2_entrant_id="2",
        status=status,
        **extra,
    )


# ── Candidate selection ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_candidates_scoped_to_event(setup_test_db):
    await _seed_candidate("t8_1", EVENT_T8, "Tekken 8")
    await _seed_candidate("t8_2", EVENT_T8, "Tekken 8")
    await _seed_candidate("sf6_1", EVENT_SF6, "SF6")

    t8 = await get_dispatch_candidates(SLUG, limit=10, event_id=EVENT_T8)
    assert {m["set_id"] for m in t8} == {"t8_1", "t8_2"}

    sf6 = await get_dispatch_candidates(SLUG, limit=10, event_id=EVENT_SF6)
    assert {m["set_id"] for m in sf6} == {"sf6_1"}


@pytest.mark.asyncio
async def test_candidates_without_event_returns_all(setup_test_db):
    await _seed_candidate("t8_1", EVENT_T8, "Tekken 8")
    await _seed_candidate("sf6_1", EVENT_SF6, "SF6")
    everything = await get_dispatch_candidates(SLUG, limit=10)
    assert {m["set_id"] for m in everything} == {"t8_1", "sf6_1"}


@pytest.mark.asyncio
async def test_stream_flagged_match_is_dispatchable(setup_test_db):
    # workflows.json: a stream-flagged match flows not_started → called like any
    # other (binding happens later, at in_progress). It must NOT be excluded just
    # because the Hub also added it to the planned_streams wishlist.
    from backend.core.database import add_planned_stream
    await _seed_candidate("stream_1", EVENT_T8, "Tekken 8", is_stream_match=1)
    await add_planned_stream("stream_1", SLUG)

    cands = await get_dispatch_candidates(SLUG, limit=10, event_id=EVENT_T8)
    ids = {m["set_id"] for m in cands}
    assert "stream_1" in ids
    # And dispatch does NOT pre-bind a station — that's deferred to in_progress.
    assert next(m for m in cands if m["set_id"] == "stream_1")["station_id"] in (None, "")


# ── Concurrency / Top-N counts ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_active_dispatched_scoped_per_event(setup_test_db):
    await _seed_candidate("t8_1", EVENT_T8, "Tekken 8", status="in_progress")
    await _seed_candidate("t8_2", EVENT_T8, "Tekken 8", status="called")
    await _seed_candidate("sf6_1", EVENT_SF6, "SF6", status="in_progress")

    assert await count_active_dispatched(SLUG, EVENT_T8) == 2
    assert await count_active_dispatched(SLUG, EVENT_SF6) == 1
    # No event filter → whole tournament.
    assert await count_active_dispatched(SLUG) == 3


@pytest.mark.asyncio
async def test_remaining_scoped_per_event(setup_test_db):
    await _seed_candidate("t8_1", EVENT_T8, "Tekken 8")
    await _seed_candidate("t8_2", EVENT_T8, "Tekken 8")
    await _seed_candidate("sf6_1", EVENT_SF6, "SF6", status="complete")

    # SF6's only match is complete → its Top-N threshold is independent of T8.
    assert await count_remaining_event_matches(SLUG, EVENT_T8) == 2
    assert await count_remaining_event_matches(SLUG, EVENT_SF6) == 0


# ── Eligible events ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_eligible_events_lists_each_event(setup_test_db):
    await _arm_tournament(concurrency=3, stop_at=4)
    await _seed_candidate("t8_1", EVENT_T8, "Tekken 8")
    await _seed_candidate("sf6_1", EVENT_SF6, "SF6")

    events = await get_dispatch_eligible_events()
    by_event = {e["event_id"]: e for e in events}
    assert set(by_event) == {EVENT_T8, EVENT_SF6}
    assert by_event[EVENT_T8]["auto_dispatch_concurrency"] == 3
    assert by_event[EVENT_T8]["auto_dispatch_stop_at"] == 4
    assert by_event[EVENT_SF6]["event_name"] == "SF6"


# ── stop_at = 0 must be honored (falsy-zero regression) ───────────────────
def test_resolve_dispatch_budget_honors_explicit_zero():
    # The bug: stop_at=0 became 8 via `int(value or 8)`.
    assert resolve_dispatch_budget({"auto_dispatch_concurrency": 2, "auto_dispatch_stop_at": 0}) == (2, 0)
    # None (genuinely unset) still falls back to the defaults.
    assert resolve_dispatch_budget({}) == (1, 8)
    # Concurrency is clamped to at least 1.
    assert resolve_dispatch_budget({"auto_dispatch_concurrency": 0, "auto_dispatch_stop_at": 5}) == (1, 5)


@pytest.mark.asyncio
async def test_eligible_events_round_trips_stop_at_zero(setup_test_db):
    # The dispatcher reads stop_at live from the DB — a TO-set 0 must survive.
    await _arm_tournament(concurrency=1, stop_at=0)
    await _seed_candidate("t8_1", EVENT_T8, "Tekken 8")

    events = await get_dispatch_eligible_events()
    assert events and events[0]["auto_dispatch_stop_at"] == 0
    assert resolve_dispatch_budget(events[0]) == (1, 0)


@pytest.mark.asyncio
async def test_disarmed_tournament_not_eligible(setup_test_db):
    # Tournament inserted but auto_dispatch_enabled stays 0.
    await upsert_tournament(SLUG, "Major X", "", "", "", "{}")
    await _seed_candidate("t8_1", EVENT_T8, "Tekken 8")
    assert await get_dispatch_eligible_events() == []


# ── Stream station routing (green room) ───────────────────────────────────
@pytest.mark.asyncio
async def test_available_stream_station_matches_event(setup_test_db):
    await create_station("s_t8", "Tekken Stream")
    await update_station("s_t8", is_stream_station=1, event_id=EVENT_T8,
                         room_name_or_id="T8-LOBBY", room_password="1111")
    await create_station("s_sf6", "SF6 Stream")
    await update_station("s_sf6", is_stream_station=1, event_id=EVENT_SF6)

    got = await get_available_stream_station(EVENT_T8)
    assert got is not None and got["id"] == "s_t8"
    assert got["room_name_or_id"] == "T8-LOBBY"

    # A different event resolves to its own station, never the T8 one.
    other = await get_available_stream_station(EVENT_SF6)
    assert other is not None and other["id"] == "s_sf6"


@pytest.mark.asyncio
async def test_non_stream_station_never_selected(setup_test_db):
    await create_station("s_plain", "Plain Setup")
    await update_station("s_plain", is_stream_station=0, event_id=EVENT_T8)
    assert await get_available_stream_station(EVENT_T8) is None


@pytest.mark.asyncio
async def test_occupied_stream_station_excluded(setup_test_db):
    await create_station("s_t8", "Tekken Stream")
    await update_station("s_t8", is_stream_station=1, event_id=EVENT_T8)
    # A live match is occupying the station → it's no longer available.
    await _seed_candidate("t8_live", EVENT_T8, "Tekken 8",
                          status="in_progress", station_id="s_t8")
    assert await get_available_stream_station(EVENT_T8) is None


@pytest.mark.asyncio
async def test_wrong_event_stream_station_excluded(setup_test_db):
    await create_station("s_sf6", "SF6 Stream")
    await update_station("s_sf6", is_stream_station=1, event_id=EVENT_SF6)
    # Asking for a T8 station must not return the SF6-bound one.
    assert await get_available_stream_station(EVENT_T8) is None
