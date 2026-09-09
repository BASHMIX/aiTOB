"""Capability profiles are local metadata and cannot expose provider secrets."""
from __future__ import annotations

from unittest.mock import AsyncMock

from backend.core.provider_projection import provider_capability_projection, tournament_provider_projection
from backend.core.providers.startgg.provider import StartGGProvider


def test_startgg_v2_profile_is_non_secret_and_declares_local_stream_removal():
    provider = StartGGProvider(client=AsyncMock(token="must-not-appear"))
    projection = tournament_provider_projection(
        {
            "provider_type": "startgg",
            "provider_tournament_id": "tournament-1",
            "provider_subdomain": None,
        },
        provider,
    )

    actions = {item["action"]: item for item in projection["actions"]}
    assert projection["contract_version"] == "v2"
    assert projection["provider_tournament_id"] == "tournament-1"
    assert actions["report_score"]["availability"] == "remote"
    assert actions["remove_stream"]["availability"] == "local"
    assert "must-not-appear" not in str(projection)


def test_legacy_profile_has_no_v2_actions_or_credentials():
    class LegacyProvider:
        provider_name = "Legacy"

    assert provider_capability_projection(LegacyProvider()) == {
        "contract_version": "legacy", "actions": []
    }


async def test_tournament_profile_route_reads_saved_identity_without_a_provider_request(monkeypatch):
    from backend.api.routers import tournaments

    client = AsyncMock(token="must-not-appear")
    provider = StartGGProvider(client=client)
    monkeypatch.setattr(
        tournaments, "get_tournament",
        AsyncMock(return_value={"slug": "fixture", "provider_type": "startgg", "provider_tournament_id": "remote-1"}),
    )
    monkeypatch.setattr(tournaments, "get_provider_for_tournament", AsyncMock(return_value=provider))

    response = await tournaments.api_provider_profile("fixture")

    assert response["provider_tournament_id"] == "remote-1"
    assert response["contract_version"] == "v2"
    client.query.assert_not_called()
