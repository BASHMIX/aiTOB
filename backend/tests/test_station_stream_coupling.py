"""Tests for commit #8 — Unassign fix + strict stream-flag ↔ station coupling.

Behavioural contract (real tournament ops):
  * PATCH {station_id: null} actually clears the station (the exclude_unset fix).
  * Rule B  — assigning a *stream* station flags the match for stream
              (+ planned-stream wishlist entry).
  * Decision 1 — assigning a *non-stream* station to a flagged match force-OFFs
              the flag (TO is pushing it off-stream) and drops it from the queue.
  * Rule C  — toggling the flag OFF unassigns the station + drops the wishlist.
  * Rule A  — toggling the flag ON routes a called/in_progress match ONLY to a
              free stream station bound to its event, never a random free setup.
"""
import os
import asyncio

import pytest
from fastapi.testclient import TestClient

import backend.core.database as db
import backend.core.match_state as ms
from backend.api.main import app

TEST_DB = "backend/core/test_station_stream_coupling.sqlite"
AUTH = {"X-Hub-Password": "admin"}
SLUG = "major/x"
EVENT = "100"

client = TestClient(app)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def patch_db():
    orig = db.DB_PATH
    db.DB_PATH = TEST_DB
    ms.DB_PATH = TEST_DB
    run(db.init_db())
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
        p1_name="A", p2_name="B", **kw,
    )


async def _seed_station(sid, name, stream=False, event_id=EVENT):
    await db.create_station(sid, name)
    await db.update_station(sid, is_stream_station=(1 if stream else 0), event_id=event_id)


def _match(set_id):
    return run(db.get_active_match(set_id))


def _planned(set_id):
    return run(db.get_planned_stream(set_id))


# ── Step 1: the Unassign bug ──────────────────────────────────────────────
def test_patch_null_station_clears_assignment():
    run(_seed_station("s_plain", "Setup 1", stream=False))
    run(_seed_match("m1", status="in_progress", station_id="s_plain"))

    resp = client.patch("/api/active-matches/m1", json={"station_id": None}, headers=AUTH)
    assert resp.status_code == 200
    assert _match("m1")["station_id"] in (None, "")


def test_patch_omitting_station_leaves_it_untouched():
    # A score-only PATCH must not wipe the station (exclude_unset, not blanket clear).
    run(_seed_station("s_plain", "Setup 1", stream=False))
    run(_seed_match("m1b", status="in_progress", station_id="s_plain", is_stream_match=0))

    resp = client.patch("/api/active-matches/m1b", json={"p1_score": 2}, headers=AUTH)
    assert resp.status_code == 200
    m = _match("m1b")
    assert m["station_id"] == "s_plain"
    assert m["p1_score"] == 2


# ── Rule B: stream station ⟹ flag ON ──────────────────────────────────────
def test_assign_stream_station_flags_match():
    run(_seed_station("s_str", "Stream A", stream=True))
    run(_seed_match("m2", status="in_progress", is_stream_match=0))

    resp = client.patch("/api/active-matches/m2", json={"station_id": "s_str"}, headers=AUTH)
    assert resp.status_code == 200
    m = _match("m2")
    assert m["station_id"] == "s_str"
    assert m["is_stream_match"]            # flagged on
    assert _planned("m2") is not None      # mirrored to the wishlist


# ── Decision 1: non-stream station ⟹ force flag OFF ───────────────────────
def test_assign_non_stream_station_forces_flag_off():
    run(_seed_station("s_plain", "Setup 1", stream=False))
    run(_seed_match("m3", status="in_progress", is_stream_match=1))
    run(db.add_planned_stream("m3", SLUG))

    resp = client.patch("/api/active-matches/m3", json={"station_id": "s_plain"}, headers=AUTH)
    assert resp.status_code == 200
    m = _match("m3")
    assert m["station_id"] == "s_plain"
    assert not m["is_stream_match"]        # strictly un-flagged
    assert _planned("m3") is None          # pulled from the wishlist


# ── Rule C: flag OFF ⟹ unassign station ───────────────────────────────────
def test_toggle_stream_off_unassigns_station():
    run(_seed_station("s_str", "Stream A", stream=True))
    run(_seed_match("m4", status="in_progress", is_stream_match=1, station_id="s_str"))
    run(db.add_planned_stream("m4", SLUG))

    resp = client.post("/api/active-matches/m4/toggle-stream",
                       json={"is_stream_match": False}, headers=AUTH)
    assert resp.status_code == 200
    m = _match("m4")
    assert not m["is_stream_match"]
    assert m["station_id"] in (None, "")   # station released
    assert _planned("m4") is None


# ── Rule A: flag ON ⟹ only a stream station for the match's event ──────────
def test_toggle_stream_on_routes_to_stream_station_only():
    run(_seed_station("s_plain", "Plain", stream=False))
    run(_seed_station("s_str", "Stream A", stream=True))
    run(_seed_match("m5", status="called", is_stream_match=0))

    resp = client.post("/api/active-matches/m5/toggle-stream",
                       json={"is_stream_match": True}, headers=AUTH)
    assert resp.status_code == 200
    m = _match("m5")
    assert m["is_stream_match"]
    assert m["station_id"] == "s_str"      # the stream station, never the plain one


def test_toggle_stream_on_without_free_stream_station_stays_unassigned():
    # Only a station bound to a DIFFERENT event exists → nothing valid to route to.
    run(_seed_station("s_other", "Other Game Stream", stream=True, event_id="999"))
    run(_seed_match("m6", status="called", is_stream_match=0))

    resp = client.post("/api/active-matches/m6/toggle-stream",
                       json={"is_stream_match": True}, headers=AUTH)
    assert resp.status_code == 200
    m = _match("m6")
    assert m["is_stream_match"]             # flag still set
    assert m["station_id"] in (None, "")   # but left for the dispatcher to place
