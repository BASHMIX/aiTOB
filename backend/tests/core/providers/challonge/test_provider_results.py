"""Phase 7B: Challonge v2.1 score payload and read-only verification evidence."""
from __future__ import annotations

import pytest

from backend.core.providers.challonge.provider import ChallongeProvider


class _Client:
    def __init__(self):
        self.update_calls: list[tuple] = []
        self.participant_calls = 0
        self.match_calls = 0

    async def update_match(self, tournament_id, match_id, attributes, community_id=None):
        self.update_calls.append((tournament_id, match_id, attributes, community_id))
        return {"id": match_id, "attributes": {"state": "complete"}}

    async def participants(self, _tournament_id, _community=None):
        self.participant_calls += 1
        return [
            {"id": "p1", "attributes": {"name": "Alpha"}},
            {"id": "p2", "attributes": {"name": "Bravo"}},
        ]

    async def matches(self, _tournament_id, _community=None):
        self.match_calls += 1
        return [{
            "id": "m1",
            "attributes": {
                "state": "complete", "winner_id": "p1", "revision": "11",
                "points_by_participant": [
                    {"participant_id": "p1", "score": 2},
                    {"participant_id": "p2", "score": 0},
                ],
            },
        }]


@pytest.mark.asyncio
async def test_score_uses_v21_match_score_set_payload(monkeypatch):
    monkeypatch.setenv("CHALLONGE_SCORE_COMMANDS_ENABLED", "true")
    client = _Client()
    provider = ChallongeProvider(client, provider_account_id="account")

    result = await provider.report_score("challonge:fnc-jo:123:m1", "p1", "p1", "p2", 2, 0)

    assert result.success is True
    assert client.update_calls == [(
        "123", "m1",
        {
            "match": [
                {"participant_id": "p1", "score_set": "2", "advancing": True},
                {"participant_id": "p2", "score_set": "0", "advancing": False},
            ],
        },
        "fnc-jo",
    )]
    assert "points_by_participant" not in client.update_calls[0][2]
    assert "scores_csv" not in client.update_calls[0][2]


@pytest.mark.asyncio
async def test_targeted_result_verification_checks_winner_points_and_entrants(monkeypatch):
    monkeypatch.setenv("CHALLONGE_SCORE_COMMANDS_ENABLED", "true")
    client = _Client()
    provider = ChallongeProvider(client, provider_account_id="account")

    verified = await provider.verify_reported_score(
        "challonge:fnc-jo:123:m1", winner_id="p1", entrant1_id="p1", entrant2_id="p2",
        entrant1_score=2, entrant2_score=0,
    )

    assert verified is True
    # One scoped snapshot, which is a read only participant cache fill plus one
    # paginated match read—not an unrelated full-bracket mutation.
    assert (client.participant_calls, client.match_calls, client.update_calls) == (1, 1, [])


@pytest.mark.asyncio
async def test_disabled_flag_does_not_issue_a_score_mutation(monkeypatch):
    monkeypatch.delenv("CHALLONGE_SCORE_COMMANDS_ENABLED", raising=False)
    client = _Client()
    result = await ChallongeProvider(client).report_score("challonge:123:m1", "p1", "p1", "p2", 2, 0)

    assert result.success is False
    assert client.update_calls == []
