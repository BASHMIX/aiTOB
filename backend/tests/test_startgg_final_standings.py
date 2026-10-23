"""Tests for Start.gg final standings queries, mapping, and completion evidence."""

from __future__ import annotations

import pytest
from backend.core.contracts.tournament_types import SnapshotScope
from backend.core.providers.startgg import mapper


def test_map_event_standings_completed():
    """Verify mapping completed event with ordered standings and ties."""
    raw_event = {
        "id": "1001",
        "name": "Tekken 8 Singles",
        "state": "COMPLETED",
        "videogame": {"id": "49783", "name": "Tekken 8"},
        "standings": {
            "pageInfo": {
                "page": 1,
                "perPage": 10,
                "totalPages": 1,
                "total": 3,
            },
            "nodes": [
                {
                    "placement": 1,
                    "entrant": {
                        "id": "e-1",
                        "name": "DRX | Knee",
                        "participants": [{
                            "id": "p-1",
                            "gamerTag": "Knee",
                            "prefix": "DRX",
                            "user": {
                                "id": "u-1",
                                "location": {"country": "KR"},
                                "images": [{"type": "profile", "url": "https://example.com/knee.png"}],
                            },
                        }],
                    },
                },
                {
                    "placement": 2,
                    "entrant": {
                        "id": "e-2",
                        "name": "Arslan Ash",
                        "participants": [{
                            "id": "p-2",
                            "gamerTag": "Arslan Ash",
                            "prefix": None,
                            "user": {
                                "id": "u-2",
                                "location": {"country": "PK"},
                                "images": [],
                            },
                        }],
                    },
                },
                {
                    "placement": 2,
                    "entrant": {
                        "id": "e-3",
                        "name": "Atif Butt",
                        "participants": [{
                            "id": "p-3",
                            "gamerTag": "Atif Butt",
                            "user": {
                                "id": "u-3",
                                "location": {"country": "PK"},
                            },
                        }],
                    },
                },
            ],
        },
    }

    result = mapper.map_event_standings(raw_event)
    assert result.event_id == "1001"
    assert result.event_name == "Tekken 8 Singles"
    assert result.game_name == "Tekken 8"
    assert result.is_completed is True
    assert result.completion_state_raw == "COMPLETED"
    assert len(result.standings) == 3

    # Entrant 1
    e1 = result.standings[0]
    assert e1.placement == 1
    assert e1.ordinal == 1
    assert e1.entrant_id == "e-1"
    assert e1.entrant_name == "DRX | Knee"
    assert e1.prefix == "DRX"
    assert e1.country == "KR"
    assert e1.avatar_url == "https://example.com/knee.png"
    assert e1.is_tied is False

    # Entrant 2 and 3 tied at 2nd
    e2 = result.standings[1]
    e3 = result.standings[2]
    assert e2.placement == 2
    assert e2.is_tied is True
    assert e3.placement == 2
    assert e3.is_tied is True

    assert result.page.total_entries == 3
    assert result.page.has_more is False
    assert result.page.is_complete is True


def test_map_event_standings_active_or_incomplete():
    """Verify active event is not marked completed and has provisional status."""
    raw_event = {
        "id": "1002",
        "name": "SF6 Singles",
        "state": "ACTIVE",
        "videogame": {"name": "Street Fighter 6"},
        "standings": {
            "pageInfo": {"page": 1, "perPage": 8, "totalPages": 2, "total": 16},
            "nodes": [
                {"placement": 1, "entrant": {"id": "e-1", "name": "Player 1"}},
            ],
        },
    }

    result = mapper.map_event_standings(raw_event)
    assert result.event_id == "1002"
    assert result.is_completed is False
    assert result.completion_state_raw == "ACTIVE"
    assert result.page.has_more is True


def test_map_event_standings_null_and_duplicate_placements():
    """Verify standings safely handle null placement or duplicate entrant IDs."""
    raw_event = {
        "id": "1003",
        "name": "Guilty Gear Strive",
        "state": "COMPLETED",
        "standings": {
            "pageInfo": {"page": 1, "perPage": 10, "totalPages": 1, "total": 3},
            "nodes": [
                {"placement": 1, "entrant": {"id": "e-1", "name": "P1"}},
                {"placement": None, "entrant": {"id": "e-2", "name": "P2"}},
                {"placement": 1, "entrant": {"id": "e-1", "name": "P1 Duplicate"}},
            ],
        },
    }

    result = mapper.map_event_standings(raw_event)
    assert len(result.warnings) > 0
    # Placements with None are omitted or flagged
    valid_placements = [s.placement for s in result.standings]
    assert None not in valid_placements
    # Entrant IDs are deduplicated
    assert len([s for s in result.standings if s.entrant_id == "e-1"]) == 1


@pytest.mark.asyncio
async def test_startgg_provider_fetch_snapshot_final_standings():
    from unittest.mock import AsyncMock
    from backend.core.contracts import ProviderSnapshotRequestV2
    from backend.core.providers.startgg.provider import StartGGProvider

    client = AsyncMock()
    client.fetch_event_standings.return_value = {
        "event": {
            "id": "2001",
            "name": "Guilty Gear Strive Top 8",
            "state": "COMPLETED",
            "videogame": {"name": "Guilty Gear -Strive-"},
            "standings": {
                "pageInfo": {"page": 1, "perPage": 8, "totalPages": 1, "total": 1},
                "nodes": [
                    {"placement": 1, "entrant": {"id": "e-10", "name": "SolBadguy"}},
                ],
            },
        }
    }
    provider = StartGGProvider(client=client)
    req = ProviderSnapshotRequestV2(
        provider_type="startgg",
        provider_account_id="acc-1",
        tournament_id="tourney-1",
        scope=SnapshotScope.FINAL_STANDINGS,
        options={"event_id": "2001", "page": 1, "per_page": 8},
    )
    snapshot = await provider.fetch_snapshot(req)

    assert SnapshotScope.FINAL_STANDINGS in snapshot.covered_scopes
    results = snapshot.payload["event_results"]
    assert results.event_id == "2001"
    assert results.is_completed is True
    assert len(results.standings) == 1
    assert results.standings[0].entrant_name == "SolBadguy"
    client.fetch_event_standings.assert_awaited_once_with("2001", page=1, per_page=8)


@pytest.mark.asyncio
async def test_startgg_provider_reads_more_than_ten_pages_with_global_ordinals():
    """Large events must not truncate at the former ten-page safety cap."""
    from unittest.mock import AsyncMock
    from backend.core.contracts import ProviderSnapshotRequestV2
    from backend.core.providers.startgg.provider import StartGGProvider

    client = AsyncMock()

    def page_payload(_event_id: str, *, page: int, per_page: int):
        return {
            "event": {
                "id": "large-event",
                "name": "Large Final Standings",
                "state": "COMPLETED",
                "standings": {
                    "pageInfo": {"page": page, "perPage": per_page, "totalPages": 11, "total": 11},
                    "nodes": [
                        {
                            "placement": page,
                            "entrant": {"id": f"entrant-{page}", "name": f"Player {page}"},
                        }
                    ],
                },
            }
        }

    client.fetch_event_standings.side_effect = page_payload
    provider = StartGGProvider(client=client)
    request = ProviderSnapshotRequestV2(
        provider_type="startgg",
        provider_account_id="acc-large",
        tournament_id="t-large",
        scope=SnapshotScope.FINAL_STANDINGS,
        options={"event_id": "large-event", "all_pages": True, "per_page": 1},
    )

    snapshot = await provider.fetch_snapshot(request)
    results = snapshot.payload["event_results"]

    assert client.fetch_event_standings.await_count == 11
    assert [entry.ordinal for entry in results.standings] == list(range(1, 12))
    assert [entry.placement for entry in results.standings] == list(range(1, 12))
    assert results.page.is_complete is True
    assert results.page.has_more is False


@pytest.mark.asyncio
async def test_startgg_provider_recomputes_ties_across_pages():
    from unittest.mock import AsyncMock
    from backend.core.contracts import ProviderSnapshotRequestV2
    from backend.core.providers.startgg.provider import StartGGProvider

    client = AsyncMock()

    def page_payload(_event_id: str, *, page: int, per_page: int):
        return {
            "event": {
                "id": "tie-event",
                "name": "Tie Event",
                "state": "COMPLETED",
                "standings": {
                    "pageInfo": {"page": page, "perPage": per_page, "totalPages": 2, "total": 2},
                    "nodes": [{"placement": 1, "entrant": {"id": f"entrant-{page}", "name": f"P{page}"}}],
                },
            }
        }

    client.fetch_event_standings.side_effect = page_payload
    provider = StartGGProvider(client=client)
    snapshot = await provider.fetch_snapshot(ProviderSnapshotRequestV2(
        provider_type="startgg",
        provider_account_id="acc-tie",
        tournament_id="t-tie",
        scope=SnapshotScope.FINAL_STANDINGS,
        options={"event_id": "tie-event", "all_pages": True, "per_page": 1},
    ))

    results = snapshot.payload["event_results"]
    assert [entry.is_tied for entry in results.standings] == [True, True]
    assert results.page.is_complete is True


@pytest.mark.asyncio
async def test_startgg_provider_cross_page_duplicate_fails_complete_evidence():
    from unittest.mock import AsyncMock
    from backend.core.contracts import ProviderSnapshotRequestV2
    from backend.core.providers.startgg.provider import StartGGProvider

    client = AsyncMock()

    def page_payload(_event_id: str, *, page: int, per_page: int):
        return {
            "event": {
                "id": "duplicate-event",
                "name": "Duplicate Event",
                "state": "COMPLETED",
                "standings": {
                    "pageInfo": {"page": page, "perPage": per_page, "totalPages": 2, "total": 2},
                    "nodes": [{"placement": page, "entrant": {"id": "same-entrant", "name": "P"}}],
                },
            }
        }

    client.fetch_event_standings.side_effect = page_payload
    provider = StartGGProvider(client=client)
    snapshot = await provider.fetch_snapshot(ProviderSnapshotRequestV2(
        provider_type="startgg",
        provider_account_id="acc-dup",
        tournament_id="t-dup",
        scope=SnapshotScope.FINAL_STANDINGS,
        options={"event_id": "duplicate-event", "all_pages": True, "per_page": 1},
    ))

    results = snapshot.payload["event_results"]
    assert len(results.standings) == 1
    assert results.page.is_complete is False
    assert any("Duplicate entrant" in warning for warning in results.warnings)
