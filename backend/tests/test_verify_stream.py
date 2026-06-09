"""Tests for the stream preflight gate (GET /api/tournaments/{slug}/verify-stream).

The endpoint live-fetches start.gg streams and cross-references them against local
stream stations' `startgg_stream_id` binding. It is warn-but-allow: `ok` drives a
UI badge, it never blocks. We assert the four reason branches and that a stale
binding (bound id no longer on start.gg) is the precise silent-failure case.
"""
import os
import pytest

import backend.core.database as db
import backend.core.match_state as match_state
from backend.core.database import (
    init_db, upsert_tournament, create_station, update_station,
)
from backend.api.routers import tournaments as tr
from backend.core.contracts.tournament_types import ProviderStream

TEST_DB_PATH = "backend/core/test_verify_stream.sqlite"
SLUG = "tournament/verifystream"


class _FakeProvider:
    def __init__(self, streams):
        self._streams = streams

    async def fetch_streams(self, slug):
        return self._streams


@pytest.fixture
async def setup(monkeypatch):
    orig = db.DB_PATH
    db.DB_PATH = TEST_DB_PATH
    match_state.DB_PATH = TEST_DB_PATH
    await init_db()
    await upsert_tournament(SLUG, "Verify Stream", "", "", "", "{}")
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    db.DB_PATH = orig
    match_state.DB_PATH = orig


def _patch_streams(monkeypatch, streams):
    async def _fake(slug):
        return _FakeProvider(streams)
    monkeypatch.setattr(tr, "get_provider_for_tournament", _fake)


async def _stream_station(sid, name, startgg_stream_id=None):
    await create_station(sid, name)
    fields = {"is_stream_station": 1}
    if startgg_stream_id is not None:
        fields["startgg_stream_id"] = startgg_stream_id
    await update_station(sid, **fields)


# ── linked: bound id still exists on start.gg → ok ──────────────────────────
@pytest.mark.asyncio
async def test_linked_station_is_ok(setup, monkeypatch):
    _patch_streams(monkeypatch, [ProviderStream(id="555", name="Main Stage", source="TWITCH")])
    await _stream_station("s1", "Main Stage", startgg_stream_id="555")

    res = await tr.api_verify_tournament_stream(SLUG)

    assert res["ok"] is True
    assert res["reason"] == "ok"
    assert res["warning"] is None
    assert res["stations"][0]["status"] == "linked"


# ── stale: bound id gone from start.gg → the silent-failure case ─────────────
@pytest.mark.asyncio
async def test_stale_binding_warns(setup, monkeypatch):
    # start.gg now returns a DIFFERENT stream id than what the station is bound to.
    _patch_streams(monkeypatch, [ProviderStream(id="999", name="Other", source="TWITCH")])
    await _stream_station("s1", "Main Stage", startgg_stream_id="555")

    res = await tr.api_verify_tournament_stream(SLUG)

    assert res["ok"] is False
    assert res["reason"] == "unlinked"
    assert res["stations"][0]["status"] == "stale"


# ── unmapped + name match → advisory suggestion, still not ok ────────────────
@pytest.mark.asyncio
async def test_unmapped_offers_name_suggestion(setup, monkeypatch):
    _patch_streams(monkeypatch, [ProviderStream(id="555", name="Main Stage", source="TWITCH")])
    await _stream_station("s1", "Main Stage", startgg_stream_id=None)

    res = await tr.api_verify_tournament_stream(SLUG)

    assert res["ok"] is False
    assert res["reason"] == "unlinked"
    st = res["stations"][0]
    assert st["status"] == "unmapped"
    assert st["suggested_stream_id"] == "555"  # name-fallback hint, never auto-bound


# ── start.gg has zero streams → distinct reason ─────────────────────────────
@pytest.mark.asyncio
async def test_no_startgg_streams(setup, monkeypatch):
    _patch_streams(monkeypatch, [])
    await _stream_station("s1", "Main Stage", startgg_stream_id="555")

    res = await tr.api_verify_tournament_stream(SLUG)

    assert res["ok"] is False
    assert res["reason"] == "no_startgg_streams"


# ── no local stream stations → most-broken case still warns (consistency) ────
@pytest.mark.asyncio
async def test_no_stream_stations(setup, monkeypatch):
    _patch_streams(monkeypatch, [ProviderStream(id="555", name="Main Stage", source="TWITCH")])
    # A non-stream station must not count.
    await create_station("rig1", "Side setup")

    res = await tr.api_verify_tournament_stream(SLUG)

    assert res["ok"] is False
    assert res["reason"] == "no_stream_stations"
    assert res["stations"] == []


# ── side effect: live fetch refreshes the cached stream list ────────────────
@pytest.mark.asyncio
async def test_verify_refreshes_cache(setup, monkeypatch):
    _patch_streams(monkeypatch, [ProviderStream(id="555", name="Main Stage", source="TWITCH")])
    await _stream_station("s1", "Main Stage", startgg_stream_id="555")

    await tr.api_verify_tournament_stream(SLUG)

    cached = await db.get_tournament_streams(SLUG)
    assert [c["id"] for c in cached] == ["555"]
