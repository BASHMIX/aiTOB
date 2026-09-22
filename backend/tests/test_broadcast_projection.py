"""Contract asserting that existing station/OBS projections do NOT adopt or invoke the new player-presentation domain in v1."""

from __future__ import annotations
import sys

import pytest

from backend.core import database
from backend.core.broadcast_projection import get_station_broadcast_state, apply_tournament_entrant_metadata


@pytest.mark.asyncio
async def test_station_broadcast_state_does_not_invoke_player_presentation_domain(postgres_repository_database, monkeypatch):
    """Assert existing station/OBS broadcast projection stays on its independent projection pipeline

    and never calls or depends on the player-presentation hook domain.
    """
    workspace_id = "ws-broadcast-test"
    station_id = "station-obs-1"

    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, "broadcast-ws", "Broadcast WS"),
        )
        await db.execute(
            """INSERT INTO stations (id, public_id, name, workspace_id)
               VALUES (?, ?, ?, ?)""",
            (station_id, "pub-obs-1", "Stream Station 1", workspace_id),
        )
        await db.execute(
            """INSERT INTO active_matches (
                set_id, station_id, status, p1_name, p2_name, p1_entrant_id, p2_entrant_id, workspace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("m-1", station_id, "in_progress", "P1 Name", "P2 Name", "ent-1", "ent-2", workspace_id),
        )
        await db.commit()

    # Track if player_presentation is touched
    invoked_presentation = False

    def guard_presentation(*args, **kwargs):
        nonlocal invoked_presentation
        invoked_presentation = True
        raise AssertionError("broadcast_projection must not invoke player_presentation domain")

    # If backend.core.player_presentation exists or gets imported, guard against its usage
    if "backend.core.player_presentation" in sys.modules:
        monkeypatch.setattr("backend.core.player_presentation.resolve_entrant_presentation", guard_presentation, raising=False)

    state = await get_station_broadcast_state(station_id, workspace_id)
    assert state is not None
    assert state.get("active_match") is not None
    active = state["active_match"]
    assert active.get("station_id") == station_id
    assert active.get("p1_name") == "P1 Name"

    # Must NOT have hook metadata like version v1 or provenance objects
    assert "version" not in active
    assert "presentation" not in active
    assert not isinstance(active.get("p1_name"), dict)
    assert not isinstance(active.get("p1_avatar"), dict)
    assert invoked_presentation is False
