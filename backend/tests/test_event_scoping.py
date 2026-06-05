"""Tests for event-scoping of active matches (multi-event tournaments).

Verifies get_active_matches() filters by event_id so a tournament hosting two
games (e.g. Tekken 8 + SF6) doesn't cross-contaminate the hub.
"""
import os
import pytest

from backend.core.database import (
    init_db, upsert_active_match, get_active_matches,
)

TEST_DB_PATH = "backend/core/test_event_scoping.sqlite"


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


async def _seed_two_events():
    # Two events under the same tournament slug.
    await upsert_active_match("t8_1", tournament_slug="major/x", event_id="100", event_name="Tekken 8", p1_name="A", p2_name="B")
    await upsert_active_match("t8_2", tournament_slug="major/x", event_id="100", event_name="Tekken 8", p1_name="C", p2_name="D")
    await upsert_active_match("sf6_1", tournament_slug="major/x", event_id="200", event_name="SF6", p1_name="E", p2_name="F")


@pytest.mark.asyncio
async def test_event_filter_scopes_to_single_event(setup_test_db):
    await _seed_two_events()

    t8 = await get_active_matches("major/x", "100")
    assert {m["set_id"] for m in t8} == {"t8_1", "t8_2"}

    sf6 = await get_active_matches("major/x", "200")
    assert {m["set_id"] for m in sf6} == {"sf6_1"}


@pytest.mark.asyncio
async def test_no_event_filter_returns_all_for_tournament(setup_test_db):
    await _seed_two_events()
    everything = await get_active_matches("major/x")
    assert {m["set_id"] for m in everything} == {"t8_1", "t8_2", "sf6_1"}


@pytest.mark.asyncio
async def test_event_filter_with_unknown_event_returns_empty(setup_test_db):
    await _seed_two_events()
    none = await get_active_matches("major/x", "999")
    assert none == []
