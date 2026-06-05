"""Commit #10 Part A: unified Call-Match path + agent context hygiene.

Verifies the Hub button and the AI agent share one core that drives the state
machine (no raw status writes), that the hub_commands queue round-trips through
its (now-wired) consumer helpers, and that the agent projection hides the
discord_thread_id that was confusing the LLM.
"""
import os
import pytest

import backend.core.database as db
import backend.core.match_state as ms
from backend.core.match_state import call_match_core
from backend.core.database import (
    init_db, upsert_active_match, get_active_match,
    add_hub_command, get_pending_hub_commands, update_hub_command_status,
    set_hub_command_listener,
)
from backend.bot.agent.tool_helpers import project_match_for_agent

TEST_DB = "backend/core/test_call_match_unification.sqlite"


@pytest.fixture
async def setup_db():
    orig = db.DB_PATH
    db.DB_PATH = TEST_DB
    ms.DB_PATH = TEST_DB
    await init_db()
    yield
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass
    db.DB_PATH = orig
    ms.DB_PATH = orig


# ── A1: the unified Call-Match core ───────────────────────────────────────
@pytest.mark.asyncio
async def test_call_match_core_transitions_and_enqueues(setup_db):
    await upsert_active_match(
        "m1", tournament_slug="t", p1_name="A", p2_name="B",
        p1_entrant_id="1", p2_entrant_id="2", status="not_started",
    )

    res = await call_match_core("m1")
    assert res.get("ok")

    # State machine moved it to 'called' (not a raw write).
    assert (await get_active_match("m1"))["status"] == "called"

    # And the standard call_match command was queued for the bot to open the thread.
    pending = await get_pending_hub_commands()
    assert any(p["command_text"] == "call_match m1" for p in pending)


@pytest.mark.asyncio
async def test_call_match_core_missing_match(setup_db):
    res = await call_match_core("nope")
    assert res.get("error") == "Match not found"


@pytest.mark.asyncio
async def test_call_match_core_rejects_invalid_transition(setup_db):
    # complete → called is not allowed by workflows.json; core must surface the error.
    await upsert_active_match("m2", tournament_slug="t", p1_name="A", p2_name="B", status="complete")
    res = await call_match_core("m2")
    assert "error" in res
    assert not (await get_pending_hub_commands())  # nothing queued on a rejected call


# ── B1: the hub_commands queue round-trips through its consumer helpers ────
@pytest.mark.asyncio
async def test_hub_command_queue_drain_cycle(setup_db):
    await add_hub_command("call_match xyz")

    pending = await get_pending_hub_commands()
    assert len(pending) == 1 and pending[0]["command_text"] == "call_match xyz"

    await update_hub_command_status(pending[0]["id"], "done")
    assert await get_pending_hub_commands() == []


@pytest.mark.asyncio
async def test_add_hub_command_fires_listener(setup_db):
    # Event-driven outbox: enqueue must fire the registered listener (the bot/API
    # use this to drain immediately instead of polling).
    fired = []
    set_hub_command_listener(lambda: fired.append(1))
    try:
        await add_hub_command("call_match z")
    finally:
        set_hub_command_listener(None)
    assert fired == [1]


@pytest.mark.asyncio
async def test_listener_errors_do_not_break_enqueue(setup_db):
    # A throwing listener must never prevent the command from being durably queued.
    def _boom():
        raise RuntimeError("listener down")
    set_hub_command_listener(_boom)
    try:
        await add_hub_command("call_match q")
    finally:
        set_hub_command_listener(None)
    assert any(p["command_text"] == "call_match q" for p in await get_pending_hub_commands())


# ── A2: the agent projection hides discord_thread_id ──────────────────────
def test_project_match_for_agent_hides_thread_id_keeps_set_id():
    row = {
        "set_id": "9988", "status": "in_progress", "discord_thread_id": "55501",
        "p1_name": "A", "p2_name": "B", "p1_entrant_id": "1", "p2_entrant_id": "2",
        "station_id": "s1", "lobby_password": "secret",
    }
    out = project_match_for_agent(row)
    assert out["set_id"] == "9988"
    assert "discord_thread_id" not in out      # the field that confused the LLM
    assert "lobby_password" not in out         # only the whitelisted fields surface
    assert out["p1_entrant_id"] == "1"
