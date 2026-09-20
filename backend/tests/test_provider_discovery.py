"""Provider-neutral setup wizard discovery contracts."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.core.provider_discovery import (
    CapabilityState,
    ProviderDiscoveryError,
    ResolutionKind,
    discover,
    freshness_seconds,
    parse_locator,
)
from backend.tests.fixtures.tournament_setup.adapters import (
    FakeChallongeClient,
    FakeStartGGClient,
)
from backend.core.providers.challonge.discovery import ChallongeDiscovery
from backend.core.providers.startgg.discovery import StartGGDiscovery


def test_startgg_event_locator_preserves_full_scope():
    locator = parse_locator("startgg", "https://www.start.gg/tournament/fn-open/event/street-fighter-6")
    assert locator.kind.value == "event"
    assert locator.tournament_slug == "tournament/fn-open"
    assert locator.scope_slug == "tournament/fn-open/event/street-fighter-6"
    assert locator.canonical == locator.scope_slug


def test_startgg_tournament_locator_does_not_guess_an_event():
    locator = parse_locator("startgg", "tournament/fn-open")
    assert locator.kind.value == "tournament"
    assert locator.scope_slug is None


def test_unsafe_provider_url_is_rejected_before_adapter_use():
    with pytest.raises(ProviderDiscoveryError) as error:
        parse_locator("startgg", "https://user:secret@evil.example/tournament/fn-open")
    assert error.value.code == "invalid_locator"
    assert "secret" not in str(error.value)


@pytest.mark.asyncio
async def test_startgg_single_event_is_selected_without_persisting():
    adapter = StartGGDiscovery(FakeStartGGClient())
    result = await discover("startgg", "fixture-startgg-account", "tournament/fn-open", adapter=adapter)
    assert result.resolution is ResolutionKind.SELECTED_SCOPE
    assert result.selected_scope is not None
    assert result.selected_scope.external_id == "fixture-sgg-event-001"
    assert result.tournament.external_id == "fixture-sgg-tournament-001"
    assert result.start_in_wave.state.value == "unknown"


@pytest.mark.asyncio
async def test_challonge_is_one_explicit_bracket():
    adapter = ChallongeDiscovery(FakeChallongeClient())
    result = await discover("challonge", "fixture-challonge-account", "aitob-fixture-bracket", adapter=adapter)
    assert result.resolution is ResolutionKind.SELECTED_SCOPE
    assert result.selected_scope is not None
    assert result.selected_scope.kind == "bracket"
    assert result.selected_scope.external_id == "fixture-challonge-bracket-001"
    assert result.start_in_wave.state.value == "unsupported"


@pytest.mark.asyncio
async def test_multiple_events_require_explicit_selection():
    class MultiEventAdapter:
        async def discover(self, locator, *, account_id):
            return {
                "tournament": {"external_id": "t-1", "name": "Open"},
                "scopes": [
                    {"kind": "event", "external_id": "e-1", "name": "Singles"},
                    {"kind": "event", "external_id": "e-2", "name": "Doubles"},
                ],
                "observed_at": datetime.now(UTC).isoformat(),
            }

    result = await discover("startgg", "account-1", "tournament/open", adapter=MultiEventAdapter())
    assert result.resolution is ResolutionKind.SCOPE_SELECTION_REQUIRED
    assert result.selected_scope is None
    assert [scope.external_id for scope in result.scopes] == ["e-1", "e-2"]


def test_freshness_is_non_negative_and_uses_utc():
    now = datetime.now(UTC)
    assert freshness_seconds(now - timedelta(seconds=12), now=now) == 12
    assert freshness_seconds(now + timedelta(seconds=12), now=now) == 0
    assert freshness_seconds("malformed", now=now) > 1_000_000


def test_capability_projection_does_not_infer_remote_start_from_match_calls():
    capabilities = __import__("backend.core.provider_discovery", fromlist=["project_capabilities"]).project_capabilities("startgg")
    assert capabilities["remote_start"].state is CapabilityState.UNKNOWN
    assert capabilities["start_in_wave_write"].state is CapabilityState.UNSUPPORTED
