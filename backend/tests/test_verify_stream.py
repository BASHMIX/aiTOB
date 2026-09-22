"""Tests for the stream preflight gate (GET /api/tournaments/{slug}/verify-stream).

The endpoint live-fetches start.gg streams and cross-references them against local
stream stations' `startgg_stream_id` binding. It is warn-but-allow: `ok` drives a
UI badge, it never blocks. We assert the four reason branches and that a stale
binding (bound id no longer on start.gg) is the precise silent-failure case.
"""
import os
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

import backend.core.database as db
import backend.core.match_state as match_state
from backend.core.database import (
    init_db, upsert_tournament, create_station, update_station,
)
from backend.api.routers import tournaments as tr
from backend.core.contracts.tournament_types import ProviderStream

TEST_DATABASE_DSN = ""
SLUG = "tournament/verifystream"
PRINCIPAL = SimpleNamespace(workspace_id="workspace-stream")


class _FakeProvider:
    def __init__(self, streams):
        self._streams = streams

    async def fetch_streams(self, slug):
        return self._streams


@pytest.fixture
async def setup(monkeypatch, tmp_path):
    global TEST_DATABASE_DSN
    TEST_DATABASE_DSN = str(tmp_path / "verify-stream.pg")
    orig = db.DATABASE_DSN
    db.DATABASE_DSN = TEST_DATABASE_DSN
    match_state.DATABASE_DSN = TEST_DATABASE_DSN
    await init_db()
    async with db.dbapi.connect(TEST_DATABASE_DSN) as connection:
        await connection.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES ('workspace-stream', 'workspace-stream', 'Streams')"
        )
        await connection.execute(
            """INSERT INTO integration_accounts
               (id, owner_id, workspace_id, provider_type, external_account_id, display_name)
               VALUES ('stream-account', 'workspace-stream', 'workspace-stream', 'startgg', 'remote', 'Start.gg')"""
        )
        await connection.commit()
    await upsert_tournament(
        SLUG, "Verify Stream", "", "", "", "{}",
        provider_account_id="stream-account", workspace_id="workspace-stream",
    )
    yield
    db.DATABASE_DSN = orig
    match_state.DATABASE_DSN = orig


def _patch_streams(monkeypatch, streams):
    async def _fake(slug, workspace_id):
        assert workspace_id == "workspace-stream"
        return _FakeProvider(streams)
    monkeypatch.setattr(tr, "get_provider_for_tournament", _fake)


async def _stream_station(sid, name, startgg_stream_id=None):
    await create_station(sid, name, workspace_id="workspace-stream")
    fields = {"is_stream_station": 1}
    if startgg_stream_id is not None:
        fields["startgg_stream_id"] = startgg_stream_id
    await update_station(sid, workspace_id="workspace-stream", **fields)


# ── linked: bound id still exists on start.gg → ok ──────────────────────────
@pytest.mark.asyncio
async def test_linked_station_is_ok(setup, monkeypatch):
    _patch_streams(monkeypatch, [ProviderStream(id="555", name="Main Stage", source="TWITCH")])
    await _stream_station("s1", "Main Stage", startgg_stream_id="555")

    res = await tr.api_verify_tournament_stream(SLUG, PRINCIPAL)

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

    res = await tr.api_verify_tournament_stream(SLUG, PRINCIPAL)

    assert res["ok"] is False
    assert res["reason"] == "unlinked"
    assert res["stations"][0]["status"] == "stale"


# ── unmapped + name match → advisory suggestion, still not ok ────────────────
@pytest.mark.asyncio
async def test_unmapped_offers_name_suggestion(setup, monkeypatch):
    _patch_streams(monkeypatch, [ProviderStream(id="555", name="Main Stage", source="TWITCH")])
    await _stream_station("s1", "Main Stage", startgg_stream_id=None)

    res = await tr.api_verify_tournament_stream(SLUG, PRINCIPAL)

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

    res = await tr.api_verify_tournament_stream(SLUG, PRINCIPAL)

    assert res["ok"] is False
    assert res["reason"] == "no_startgg_streams"


# ── no local stream stations → most-broken case still warns (consistency) ────
@pytest.mark.asyncio
async def test_no_stream_stations(setup, monkeypatch):
    _patch_streams(monkeypatch, [ProviderStream(id="555", name="Main Stage", source="TWITCH")])
    # A non-stream station must not count.
    await create_station("rig1", "Side setup", workspace_id="workspace-stream")

    res = await tr.api_verify_tournament_stream(SLUG, PRINCIPAL)

    assert res["ok"] is False
    assert res["reason"] == "no_stream_stations"
    assert res["stations"] == []


@pytest.mark.asyncio
async def test_unbound_provider_is_a_configuration_conflict_not_a_500(setup, monkeypatch):
    async def _unbound(*_args, **_kwargs):
        raise ValueError("Start.gg tournament is not bound to an integration account.")

    monkeypatch.setattr(tr, "get_provider_for_tournament", _unbound)
    with pytest.raises(HTTPException) as exc_info:
        await tr.api_verify_tournament_stream(SLUG, PRINCIPAL)
    assert getattr(exc_info.value, "status_code", None) == 409


# ── side effect: live fetch refreshes the cached stream list ────────────────
@pytest.mark.asyncio
async def test_verify_refreshes_cache(setup, monkeypatch):
    _patch_streams(monkeypatch, [ProviderStream(id="555", name="Main Stage", source="TWITCH")])
    await _stream_station("s1", "Main Stage", startgg_stream_id="555")

    await tr.api_verify_tournament_stream(SLUG, PRINCIPAL)

    cached = await db.get_tournament_streams(SLUG, "workspace-stream")
    assert [c["id"] for c in cached] == ["555"]
