"""WebSocket tenant authorization acceptance for the session foundation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api.main import app
from backend.core import database
OWNER_EMAIL = "ws-owner@example.test"
OWNER_PASSWORD = "a-strong-owner-password"


@pytest.fixture()
def isolated_workspace_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "websocket.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_EMAIL", OWNER_EMAIL)
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", OWNER_PASSWORD)
    monkeypatch.setenv("AITOB_AUTH_MASTER_KEY", "7lXNrOpw2HnqGYiRkqzGN70KGyxoDpcQ0H3jDXiVlvc=")
    monkeypatch.delenv("AITOB_LEGACY_HUB_PASSWORD_COMPAT", raising=False)
    asyncio.run(database.init_db())
    return db_path


def test_hub_websocket_requires_a_live_session(isolated_workspace_db):
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as denied:
        with client.websocket_connect("/ws/hub"):
            pass
    assert denied.value.code == 4401


def test_hub_websocket_subscriptions_are_bound_to_session_workspace(isolated_workspace_db):
    async def seed():
        async with database.aiosqlite.connect(database.DB_PATH) as db:
            owner_workspace = (await (await db.execute("SELECT id FROM workspaces ORDER BY created_at LIMIT 1")).fetchone())[0]
            await db.execute("INSERT INTO workspaces (id,slug,name) VALUES ('workspace-other','workspace-other','Other')")
            await db.commit()
        await database.upsert_tournament(
            "owned-tournament", "Owned", "Event", "event-1", "Game", "{}",
            provider_type="startgg", provider_tournament_id="owned", workspace_id=owner_workspace,
        )
        await database.upsert_tournament(
            "other-tournament", "Other", "Event", "event-2", "Game", "{}",
            provider_type="startgg", provider_tournament_id="other", workspace_id="workspace-other",
        )

    import asyncio
    asyncio.run(seed())
    client = TestClient(app)
    assert client.post("/api/session/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}).status_code == 200
    with client.websocket_connect("/ws/hub") as socket:
        socket.send_text(json.dumps({"type": "subscribe", "tournament_slug": "owned-tournament"}))
        assert socket.receive_json() == {"type": "subscribed", "slug": "owned-tournament"}
        socket.send_text(json.dumps({"type": "subscribe", "tournament_slug": "other-tournament"}))
        assert socket.receive_json() == {"type": "subscription_denied"}


def test_overlay_websocket_requires_hashed_station_grant_and_cannot_cross_workspace(isolated_workspace_db):
    async def seed():
        async with database.aiosqlite.connect(database.DB_PATH) as db:
            owner_workspace = (await (await db.execute("SELECT id FROM workspaces ORDER BY created_at LIMIT 1")).fetchone())[0]
        await database.create_station("overlay-a", "Overlay A", owner_workspace)

    import asyncio
    asyncio.run(seed())
    client = TestClient(app)
    # A public overlay link is intentionally a separate, least-privilege
    # capability; no session or guessed token may authenticate it.
    with client.websocket_connect("/ws/overlay/overlay-a") as socket:
        socket.send_text(json.dumps({"type": "authenticate", "token": "not-a-grant"}))
        with pytest.raises(WebSocketDisconnect) as denied:
            socket.receive_json()
    assert denied.value.code == 4401
