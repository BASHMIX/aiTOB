"""Unit tests for station stream queue and busy player conflict detection."""
from __future__ import annotations

import asyncio
import pytest

from backend.core import database
from backend.core.broadcast_projection import get_station_broadcast_state


def run(coro):
    return asyncio.run(coro)


async def seed_matches(workspace_id: str, *set_ids: str):
    """A stream queue references real local match projections only."""
    for set_id in set_ids:
        await database.upsert_active_match({
            "set_id": set_id,
            "status": "not_started",
            "p1_name": "Player 1",
            "p2_name": "Player 2",
            "workspace_id": workspace_id,
        })


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    original_path = database.DATABASE_DSN
    database.DATABASE_DSN = str(tmp_path / "station-queue-test.pg")
    monkeypatch.setenv("AITOB_TESTING", "1")
    monkeypatch.setenv("DATABASE_DSN", database.DATABASE_DSN)
    run(database.init_db())
    yield
    database.DATABASE_DSN = original_path


def test_station_queue_enqueue_and_order():
    """Verify matches are queued in correct ascending sort_order and unique per station."""
    run(database.create_station("st-1", "Station 1", "ws-1"))
    run(seed_matches("ws-1", "match-101", "match-102", "match-103"))

    # Enqueue matches
    assert run(database.enqueue_station_match("st-1", "match-101", "ws-1")) is True
    assert run(database.enqueue_station_match("st-1", "match-102", "ws-1")) is True
    assert run(database.enqueue_station_match("st-1", "match-103", "ws-1")) is True

    # Duplicate enqueue should be ignored safely
    assert run(database.enqueue_station_match("st-1", "match-102", "ws-1")) is True

    queue = run(database.get_station_queue("st-1", "ws-1"))
    assert len(queue) == 3
    assert [item["set_id"] for item in queue] == ["match-101", "match-102", "match-103"]
    assert [item["sort_order"] for item in queue] == [0, 1, 2]


def test_station_queue_reorder_and_dequeue():
    """Verify reordering and removing from station queue."""
    run(database.create_station("st-1", "Station 1", "ws-1"))
    run(seed_matches("ws-1", "match-1", "match-2", "match-3"))
    run(database.enqueue_station_match("st-1", "match-1", "ws-1"))
    run(database.enqueue_station_match("st-1", "match-2", "ws-1"))
    run(database.enqueue_station_match("st-1", "match-3", "ws-1"))

    # Reorder to 3, 1, 2
    assert run(database.reorder_station_queue("st-1", ["match-3", "match-1", "match-2"], "ws-1")) is True
    queue = run(database.get_station_queue("st-1", "ws-1"))
    assert [item["set_id"] for item in queue] == ["match-3", "match-1", "match-2"]

    # Dequeue middle match (match-1)
    assert run(database.dequeue_station_match("st-1", "match-1", "ws-1")) is True
    queue = run(database.get_station_queue("st-1", "ws-1"))
    assert [item["set_id"] for item in queue] == ["match-3", "match-2"]
    assert [item["sort_order"] for item in queue] == [0, 1]


def test_station_queue_advance():
    """Verify advance_station_queue pops the top match and compacts remaining."""
    run(database.create_station("st-1", "Station 1", "ws-1"))
    run(seed_matches("ws-1", "match-a", "match-b"))
    run(database.enqueue_station_match("st-1", "match-a", "ws-1"))
    run(database.enqueue_station_match("st-1", "match-b", "ws-1"))

    # Advance pops match-a
    promoted = run(database.advance_station_queue("st-1", "ws-1"))
    queue = run(database.get_station_queue("st-1", "ws-1"))
    assert len(queue) == 1
    assert queue[0]["set_id"] == "match-b"
    assert queue[0]["sort_order"] == 0


def test_station_queue_rejects_an_unknown_match():
    run(database.create_station("st-1", "Station 1", "ws-1"))
    assert run(database.enqueue_station_match("st-1", "no-local-projection", "ws-1")) is False
    assert run(database.get_station_queue("st-1", "ws-1")) == []


def test_busy_player_conflict_detection():
    """Verify check_players_busy detects if a player is currently playing in another active match."""
    run(database.create_station("st-1", "Station 1", "ws-1"))
    run(database.create_station("st-2", "Station 2", "ws-1"))

    # Add match currently in progress on station 2 with player "Daigo" (entrant_id: "e-100")
    run(database.upsert_active_match({
        "set_id": "active-live-1",
        "station_id": "st-2",
        "status": "in_progress",
        "p1_name": "Daigo",
        "p1_entrant_id": "e-100",
        "p2_name": "Tokido",
        "p2_entrant_id": "e-200",
        "workspace_id": "ws-1"
    }))

    # Add another match queued on Station 1 where Daigo is playing
    run(database.upsert_active_match({
        "set_id": "queued-match-1",
        "status": "not_started",
        "p1_name": "Daigo",
        "p1_entrant_id": "e-100",
        "p2_name": "Justin Wong",
        "p2_entrant_id": "e-300",
        "workspace_id": "ws-1"
    }))
    run(database.enqueue_station_match("st-1", "queued-match-1", "ws-1"))

    # get_station_queue should flag Daigo as busy on Station 2!
    queue = run(database.get_station_queue("st-1", "ws-1"))
    assert len(queue) == 1
    busy = queue[0]["busy_players"]
    assert len(busy) == 1
    assert busy[0]["player"] == "Daigo"
    assert busy[0]["station_name"] == "Station 2"
    assert busy[0]["set_id"] == "active-live-1"


def test_broadcast_projection_next_match():
    """Verify get_station_broadcast_state returns next_match, next_match_tbd, and busy_players."""
    run(database.create_station("st-broadcast", "Main Stage", "ws-test"))

    # 1. Empty queue -> next_match is None, next_match_tbd is True
    state = run(get_station_broadcast_state("st-broadcast", "ws-test"))
    assert state is not None
    assert state["next_match"] is None
    assert state["next_match_tbd"] is True
    assert state["busy_players"] == []

    # 2. Add queued match with known players
    run(database.upsert_active_match({
        "set_id": "semi-final",
        "status": "not_started",
        "p1_name": "MenaRD",
        "p1_prefix": "BANDITS",
        "p2_name": "AngryBird",
        "p2_prefix": "NASR",
        "round_name": "Winners Semis",
        "workspace_id": "ws-test"
    }))
    run(database.enqueue_station_match("st-broadcast", "semi-final", "ws-test"))

    state = run(get_station_broadcast_state("st-broadcast", "ws-test"))
    assert state["next_match"] is not None
    assert state["next_match"]["p1_name"] == "MenaRD"
    assert state["next_match"]["p2_name"] == "AngryBird"
    assert state["next_match_tbd"] is False
    assert state["next_match"]["match_status"] == "Ready"

    # 3. Add queued match with TBD player
    run(database.upsert_active_match({
        "set_id": "grand-final",
        "status": "not_started",
        "p1_name": "MenaRD",
        "p2_name": "TBD",
        "round_name": "Grand Finals",
        "workspace_id": "ws-test"
    }))
    run(database.enqueue_station_match("st-broadcast", "grand-final", "ws-test"))
    run(database.reorder_station_queue("st-broadcast", ["grand-final", "semi-final"], "ws-test"))

    state_tbd = run(get_station_broadcast_state("st-broadcast", "ws-test"))
    assert state_tbd["next_match"] is not None
    assert state_tbd["next_match_tbd"] is True
    assert state_tbd["next_match"]["match_status"] == "Awaiting Opponent"
