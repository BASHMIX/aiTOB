from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from backend.api.routers import players, tournaments
from backend.api.ws_manager import ConnectionManager
from backend.core.providers.startgg.client import StartGGClient


@pytest.mark.asyncio
async def test_startgg_client_retries_connect_failure_before_graphql(monkeypatch):
    request = httpx.Request("POST", "https://api.start.gg/gql/alpha")
    response = httpx.Response(200, request=request, json={"data": {"event": {"id": "event-1"}}})
    http_client = SimpleNamespace(
        post=AsyncMock(side_effect=[httpx.ConnectError("offline", request=request), response])
    )
    client = StartGGClient(token="fixture")
    monkeypatch.setattr(client, "_get_http_client", AsyncMock(return_value=http_client))
    monkeypatch.setattr(client, "_handle_rate_limit", AsyncMock())
    monkeypatch.setattr(client, "_ensure_token", AsyncMock())
    sleep = AsyncMock()
    monkeypatch.setattr("backend.core.providers.startgg.client.asyncio.sleep", sleep)

    result = await client.query("query Event { event(id: 1) { id } }")

    assert result == {"event": {"id": "event-1"}}
    assert http_client.post.await_count == 2
    sleep.assert_awaited_once_with(0.5)


@pytest.mark.asyncio
async def test_startgg_client_does_not_retry_unknown_outcome_timeout(monkeypatch):
    request = httpx.Request("POST", "https://api.start.gg/gql/alpha")
    http_client = SimpleNamespace(
        post=AsyncMock(side_effect=httpx.ReadTimeout("unknown outcome", request=request))
    )
    client = StartGGClient(token="fixture")
    monkeypatch.setattr(client, "_get_http_client", AsyncMock(return_value=http_client))
    monkeypatch.setattr(client, "_handle_rate_limit", AsyncMock())
    monkeypatch.setattr(client, "_ensure_token", AsyncMock())

    with pytest.raises(httpx.ReadTimeout):
        await client.query("mutation Fixture { markSetInProgress(setId: 1) { id } }")

    assert http_client.post.await_count == 1


@pytest.mark.asyncio
async def test_game_catalog_outage_uses_only_same_event_cache(monkeypatch):
    cached = {
        "event_id": "event-sf6",
        "event_name": "FNCtestHub",
        "game_name": "Street Fighter 6",
        "characters": [{"id": "1", "name": "Ryu", "image_url": "https://cdn.example/ryu.png"}],
    }

    class OfflineProvider:
        async def fetch_event_game_metadata(self, event_id: str):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(tournaments, "get_tournament", AsyncMock(return_value={"provider_type": "startgg"}))
    monkeypatch.setattr(tournaments, "get_provider_for_tournament", AsyncMock(return_value=OfflineProvider()))
    monkeypatch.setattr(tournaments, "get_tournament_game_metadata", AsyncMock(return_value=cached))
    principal = SimpleNamespace(workspace_id="workspace-1", legacy=False)

    result = await tournaments.api_tournament_game_metadata(
        "tournament/test", "event-sf6", principal, refresh=True
    )

    assert result["metadata_source"] == "cache"
    assert result["metadata_stale"] is True
    assert result["event_id"] == "event-sf6"
    assert result["characters"] == cached["characters"]


@pytest.mark.asyncio
async def test_game_catalog_normal_render_is_cache_first(monkeypatch):
    cached = {
        "event_id": "event-sf6",
        "event_name": "FNCtestHub",
        "game_name": "Street Fighter 6",
        "characters": [{"id": "1", "name": "Ryu"}],
    }
    provider_lookup = AsyncMock(side_effect=AssertionError("normal render must not call Start.gg"))
    monkeypatch.setattr(tournaments, "get_tournament", AsyncMock(return_value={"provider_type": "startgg"}))
    monkeypatch.setattr(tournaments, "get_tournament_game_metadata", AsyncMock(return_value=cached))
    monkeypatch.setattr(tournaments, "get_provider_for_tournament", provider_lookup)
    principal = SimpleNamespace(workspace_id="workspace-1", legacy=False)

    result = await tournaments.api_tournament_game_metadata("tournament/test", "event-sf6", principal)

    assert result["metadata_source"] == "cache"
    assert result["metadata_stale"] is False
    provider_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_character_override_is_canonicalized_from_selected_event(monkeypatch):
    tournament = {
        "provider_type": "startgg",
        "raw_data": json.dumps({
            "events": [{
                "id": "event-sf6",
                "entrants": {"nodes": [{"id": "entrant-1", "name": "Player"}]},
            }],
        }),
    }
    catalog = {
        "event_id": "event-sf6",
        "characters": [{
            "id": "character-ryu",
            "name": "Ryu",
            "image_url": "https://cdn.example/ryu.png",
        }],
    }
    monkeypatch.setattr(players, "get_tournament", AsyncMock(return_value=tournament))
    monkeypatch.setattr(players, "get_tournament_game_metadata", AsyncMock(return_value=catalog))

    result = await players._canonical_character_override(
        "entrant-1",
        {
            "tournament_slug": "tournament/test",
            "event_id": "event-sf6",
            "character_id": "character-ryu",
            "character": "spoofed name",
            "character_image_url": "https://attacker.invalid/image.png",
        },
        "workspace-1",
    )

    assert result == {
        "character": "Ryu",
        "character_id": "character-ryu",
        "character_image_url": "https://cdn.example/ryu.png",
    }


@pytest.mark.asyncio
async def test_character_override_rejects_entrant_from_another_event(monkeypatch):
    tournament = {
        "provider_type": "startgg",
        "raw_data": json.dumps({
            "events": [{
                "id": "event-sf6",
                "entrants": {"nodes": [{"id": "entrant-1"}]},
            }],
        }),
    }
    monkeypatch.setattr(players, "get_tournament", AsyncMock(return_value=tournament))

    with pytest.raises(HTTPException) as error:
        await players._canonical_character_override(
            "entrant-from-tekken",
            {
                "tournament_slug": "tournament/test",
                "event_id": "event-sf6",
                "character_id": "character-ryu",
            },
            "workspace-1",
        )

    assert error.value.status_code == 409
    assert "selected Event" in str(error.value.detail)


@pytest.mark.asyncio
async def test_character_change_notifies_each_workspace_overlay_once():
    manager = ConnectionManager()

    class Socket:
        def __init__(self):
            self.send_text = AsyncMock()

    first = Socket()
    second = Socket()
    other_workspace = Socket()
    manager.overlay_connections = {
        "workspace-1:station-a": {first},
        "workspace-1:station-b": {first, second},
        "workspace-2:station-c": {other_workspace},
    }

    await manager.broadcast_to_workspace_overlays("workspace-1", {"type": "match_update"})

    first.send_text.assert_awaited_once()
    second.send_text.assert_awaited_once()
    other_workspace.send_text.assert_not_awaited()
