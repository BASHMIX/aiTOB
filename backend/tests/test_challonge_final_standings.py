"""Tests for Challonge final standings mapping and snapshot handling."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from backend.core.contracts import (
    ProviderSnapshotRequestV2,
    SnapshotScope,
)
from backend.core.providers.challonge import mapper
from backend.core.providers.challonge.provider import ChallongeProvider


def test_map_challonge_standings_completed():
    """Verify completed tournament maps standings with ties and ordinal preservation."""
    raw_tournament = {
        "id": "chl-100",
        "attributes": {
            "name": "Smash Ultimate Weekly #42",
            "state": "complete",
            "game_name": "Super Smash Bros. Ultimate",
        },
    }
    raw_participants = [
        {
            "id": "p-1",
            "attributes": {
                "name": "MkLeo",
                "username": "mkleo_ssb",
                "final_rank": 1,
            },
        },
        {
            "id": "p-2",
            "attributes": {
                "name": "Sparg0",
                "username": "sparg0_cloud",
                "final_rank": 2,
            },
        },
        {
            "id": "p-3",
            "attributes": {
                "name": "Tweek",
                "username": "tweek_diddy",
                "final_rank": 3,
            },
        },
        {
            "id": "p-4",
            "attributes": {
                "name": "Sonix",
                "username": "sonix_sonic",
                "final_rank": 3,
            },
        },
    ]

    result = mapper.map_challonge_standings(raw_tournament, raw_participants)
    assert result.event_id == "chl-100"
    assert result.event_name == "Smash Ultimate Weekly #42"
    assert result.game_name == "Super Smash Bros. Ultimate"
    assert result.is_completed is True
    assert result.completion_state_raw == "complete"
    assert len(result.standings) == 4

    # 1st place
    assert result.standings[0].placement == 1
    assert result.standings[0].ordinal == 1
    assert result.standings[0].entrant_name == "MkLeo"
    assert result.standings[0].is_tied is False

    # 2nd place
    assert result.standings[1].placement == 2
    assert result.standings[1].ordinal == 2
    assert result.standings[1].entrant_name == "Sparg0"
    assert result.standings[1].is_tied is False

    # 3rd place ties
    assert result.standings[2].placement == 3
    assert result.standings[2].ordinal == 3
    assert result.standings[2].is_tied is True

    assert result.standings[3].placement == 3
    assert result.standings[3].ordinal == 4
    assert result.standings[3].is_tied is True


def test_map_challonge_standings_awaiting_review_is_provisional():
    """Verify awaiting_review tournament remains provisional (not completed)."""
    raw_tournament = {
        "id": "chl-101",
        "attributes": {
            "name": "Tekken 8 Clash",
            "state": "awaiting_review",
            "game_name": "Tekken 8",
        },
    }
    raw_participants = [
        {
            "id": "p-10",
            "attributes": {"name": "Player 1", "final_rank": 1},
        },
        {
            "id": "p-11",
            "attributes": {"name": "Player 2", "final_rank": 2},
        },
    ]

    result = mapper.map_challonge_standings(raw_tournament, raw_participants)
    assert result.event_id == "chl-101"
    assert result.is_completed is False
    assert result.completion_state_raw == "awaiting_review"
    assert any("awaiting_review" in w for w in result.warnings)


def test_map_challonge_standings_missing_final_ranks():
    """Verify participants without final_rank produce warnings and non-completed state."""
    raw_tournament = {
        "id": "chl-102",
        "attributes": {
            "name": "Street Fighter 6 Local",
            "state": "underway",
            "game_name": "Street Fighter 6",
        },
    }
    raw_participants = [
        {
            "id": "p-20",
            "attributes": {"name": "Player 1", "final_rank": None},
        },
    ]

    result = mapper.map_challonge_standings(raw_tournament, raw_participants)
    assert result.is_completed is False
    assert result.completion_state_raw == "underway"


def test_completed_two_stage_uses_only_final_stage_ranked_participants():
    """Group-only entrants have no final_rank and must not block Final output."""
    raw_tournament = {
        "id": "chl-two-stage",
        "attributes": {
            "name": "Two Stage Finals",
            "state": "complete",
            "group_stage_enabled": True,
            "game_name": "Street Fighter 6",
        },
    }
    raw_participants = [
        {"id": "final-1", "attributes": {"name": "Winner", "final_rank": 1}},
        {"id": "final-2", "attributes": {"name": "Runner Up", "final_rank": 2}},
        {"id": "group-only", "attributes": {"name": "Pool Entrant", "final_rank": None}},
    ]

    result = mapper.map_challonge_standings(raw_tournament, raw_participants)

    assert result.is_completed is True
    assert [entry.entrant_id for entry in result.standings] == ["final-1", "final-2"]
    assert result.page.total_entries == 2
    assert any("group-stage-only" in warning for warning in result.warnings)


def test_completed_single_stage_missing_rank_is_not_final():
    raw_tournament = {
        "id": "chl-single-stage",
        "attributes": {"name": "Broken Finals", "state": "complete", "group_stage_enabled": False},
    }
    raw_participants = [
        {"id": "ranked", "attributes": {"name": "Winner", "final_rank": 1}},
        {"id": "missing", "attributes": {"name": "Unknown", "final_rank": None}},
    ]

    result = mapper.map_challonge_standings(raw_tournament, raw_participants)

    assert result.is_completed is False
    assert any("do not have final_rank" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_challonge_provider_fetch_snapshot_final_standings():
    """Verify ChallongeProvider fetches and maps FINAL_STANDINGS snapshot."""
    client = AsyncMock()
    client.get_tournament.return_value = {
        "id": "tourney-999",
        "attributes": {
            "name": "Guilty Gear Weekly",
            "state": "complete",
            "game_name": "Guilty Gear -Strive-",
        },
    }
    client.participants.return_value = [
        {
            "id": "cp-1",
            "attributes": {"name": "LeoWhitefang", "final_rank": 1},
        },
        {
            "id": "cp-2",
            "attributes": {"name": "KyKiske", "final_rank": 2},
        },
    ]

    provider = ChallongeProvider(client=client)
    req = ProviderSnapshotRequestV2(
        provider_type="challonge",
        provider_account_id="acc-ch-1",
        tournament_id="tourney-999",
        scope=SnapshotScope.FINAL_STANDINGS,
        options={},
    )
    snapshot = await provider.fetch_snapshot(req)

    assert SnapshotScope.FINAL_STANDINGS in snapshot.covered_scopes
    results = snapshot.payload["event_results"]
    assert results.event_id == "tourney-999"
    assert results.is_completed is True
    assert len(results.standings) == 2
    assert results.standings[0].entrant_name == "LeoWhitefang"
    assert results.standings[0].placement == 1
    client.get_tournament.assert_awaited_once_with("tourney-999", None)
    client.participants.assert_awaited_once_with("tourney-999", None)
