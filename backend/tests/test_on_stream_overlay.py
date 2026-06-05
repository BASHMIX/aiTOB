"""Tests for the `on_stream` overlay realized at the called → in_progress edge.

Strict workflows.json compliance (commit #9): stream coverage is a DERIVED
overlay of `in_progress` (condition: is_stream_match == true), never its own
state. So the stream station is bound at the exact moment a match enters
`in_progress`, and freed the moment it `complete`s — with no new state or
transition added to the machine.
"""
import os
import pytest

import backend.core.database as db
import backend.core.match_state as ms
from backend.core.match_state import (
    transition_match, validate_transition, VALID_TRANSITIONS, WORKFLOW_OVERLAYS,
)

TEST_DB = "backend/core/test_on_stream_overlay.sqlite"
EVENT = "100"
SLUG = "major/x"


class _DummyResult:
    success = True
    error_message = None


class _DummyProvider:
    async def mark_in_progress(self, set_id):
        return _DummyResult()


async def _dummy_get_provider(slug):
    return _DummyProvider()


@pytest.fixture
async def setup_db(monkeypatch):
    orig = db.DB_PATH
    db.DB_PATH = TEST_DB
    ms.DB_PATH = TEST_DB
    # Keep the provider mark_in_progress call hermetic (no network).
    monkeypatch.setattr(ms, "get_provider_for_tournament", _dummy_get_provider)
    await db.init_db()
    yield
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass
    db.DB_PATH = orig
    ms.DB_PATH = orig


async def _seed_match(set_id, **kw):
    await db.upsert_active_match(
        set_id, tournament_slug=SLUG, event_id=EVENT,
        p1_name="A", p2_name="B", p1_entrant_id="1", p2_entrant_id="2",
        bot_enabled=0, **kw,
    )


async def _seed_stream_station(sid, event_id=EVENT):
    await db.create_station(sid, sid)
    await db.update_station(sid, is_stream_station=1, event_id=event_id)


# ── The overlay is a derived view, never a transition target ───────────────
def test_on_stream_is_not_a_transition_target():
    assert "on_stream" not in VALID_TRANSITIONS
    assert not validate_transition("in_progress", "on_stream")
    assert WORKFLOW_OVERLAYS["on_stream"]["derived_from"] == "in_progress"


# ── Step 3: bind the station exactly at called → in_progress ───────────────
@pytest.mark.asyncio
async def test_in_progress_binds_event_matching_stream_station(setup_db):
    await _seed_stream_station("s_str")
    await _seed_match("m1", status="called", is_stream_match=1)

    res = await transition_match("m1", "in_progress")
    assert res.get("ok")
    m = await db.get_active_match("m1")
    assert m["status"] == "in_progress"
    assert m["station_id"] == "s_str"


@pytest.mark.asyncio
async def test_in_progress_non_stream_match_binds_nothing(setup_db):
    await _seed_stream_station("s_str")
    await _seed_match("m2", status="called", is_stream_match=0)

    await transition_match("m2", "in_progress")
    m = await db.get_active_match("m2")
    assert m["station_id"] in (None, "")


@pytest.mark.asyncio
async def test_in_progress_no_free_station_proceeds_unbound(setup_db):
    # Only a station for a DIFFERENT event exists → nothing valid to bind.
    await _seed_stream_station("s_other", event_id="999")
    await _seed_match("m3", status="called", is_stream_match=1)

    res = await transition_match("m3", "in_progress")
    assert res.get("ok")                       # transition is NEVER blocked
    m = await db.get_active_match("m3")
    assert m["status"] == "in_progress"
    assert m["station_id"] in (None, "")


# ── Step 4: free the station the instant the match completes ───────────────
@pytest.mark.asyncio
async def test_complete_frees_station(setup_db):
    await _seed_stream_station("s_str")
    await _seed_match("m4", status="in_progress", is_stream_match=1, station_id="s_str")

    await transition_match("m4", "complete")
    m = await db.get_active_match("m4")
    assert m["status"] == "complete"
    assert m["station_id"] in (None, "")
    # And the freed station is immediately available again.
    assert (await db.get_available_stream_station(EVENT))["id"] == "s_str"
