from __future__ import annotations

import pytest

from backend.core.contracts import ProviderSnapshotRequestV2, SnapshotScope
from backend.core.providers.challonge.provider import ChallongeProvider


class _Client:
    def __init__(self):
        self.participant_calls = 0
        self.match_calls = 0
        self.mutations = 0

    async def participants(self, *_args):
        self.participant_calls += 1
        return [{"id": "p1", "attributes": {"name": "Alpha"}}, {"id": "p2", "attributes": {"name": "Bravo"}}]

    async def matches(self, *_args):
        self.match_calls += 1
        return [{"id": "m1", "attributes": {"state": "open", "player1_id": "p1", "player2_id": "p2"}}]

    async def get_tournament(self, *_args):
        return {"id": "1", "attributes": {"name": "FNC"}}


def _request(scope, **kwargs):
    return ProviderSnapshotRequestV2(
        provider_type="challonge", provider_account_id="account", tournament_id="1",
        scope=scope, **kwargs,
    )


@pytest.mark.asyncio
async def test_full_snapshot_uses_paginated_participants_and_matches_then_declares_coverage():
    client = _Client()
    provider = ChallongeProvider(client)

    snapshot = await provider.fetch_snapshot(_request(SnapshotScope.FULL_SNAPSHOT))

    assert client.participant_calls == client.match_calls == 1
    assert len(snapshot.payload["sets"]) == 1
    assert SnapshotScope.FULL_SNAPSHOT in snapshot.covered_scopes
    assert SnapshotScope.PARTICIPANTS in snapshot.covered_scopes


@pytest.mark.asyncio
async def test_participant_ttl_avoids_repeat_read_and_targeted_scope_only_returns_requested_match():
    client = _Client()
    provider = ChallongeProvider(client)
    await provider.fetch_snapshot(_request(SnapshotScope.ACTIVE_MATCHES))
    snapshot = await provider.fetch_snapshot(
        _request(SnapshotScope.SINGLE_MATCH, entity_ids=frozenset({"m1"}))
    )

    assert client.participant_calls == 1
    assert client.match_calls == 2
    assert [item.provider_set_id for item in snapshot.payload["sets"]] == ["m1"]
    assert snapshot.covered_entity_ids == frozenset({"m1"})
