"""Candidate DQ payloads are sandbox-gated and never dispatched in Phase 9A."""
from __future__ import annotations

import pytest

from backend.core.contracts import ProviderActionKind
from backend.core.providers.challonge.forfeit_policy import ForfeitPolicy, ForfeitUnsupported
from backend.core.providers.challonge.provider import ChallongeProvider


def test_candidate_preserves_slot_one_winner_with_public_0_minus_1_candidate():
    candidate = ForfeitPolicy.candidate(winner_id="p1", entrant1_id="p1", entrant2_id="p2")
    assert candidate.attributes() == {
        "match": [
            {"participant_id": "p1", "score_set": "0", "advancing": True},
            {"participant_id": "p2", "score_set": "-1", "advancing": False},
        ]
    }
    assert "scores_csv" not in candidate.attributes()


def test_candidate_preserves_slot_two_winner_with_public_0_minus_1_candidate():
    candidate = ForfeitPolicy.candidate(winner_id="p2", entrant1_id="p1", entrant2_id="p2")
    assert candidate.attributes()["match"] == [
        {"participant_id": "p1", "score_set": "-1", "advancing": False},
        {"participant_id": "p2", "score_set": "0", "advancing": True},
    ]


def test_double_dq_or_missing_winner_is_not_representable():
    with pytest.raises(ForfeitUnsupported):
        ForfeitPolicy.candidate(winner_id="", entrant1_id="p1", entrant2_id="p2")


def test_provider_exposes_single_player_forfeit_only_when_both_opt_in_flags_are_enabled(monkeypatch):
    monkeypatch.setenv("CHALLONGE_SCORE_COMMANDS_ENABLED", "true")
    monkeypatch.setenv("CHALLONGE_DQ_COMMANDS_ENABLED", "true")
    provider = ChallongeProvider()
    assert provider.capabilities_v2.for_action("report_forfeit").kind is ProviderActionKind.REMOTE


def test_provider_hides_single_player_forfeit_without_explicit_dq_opt_in(monkeypatch):
    monkeypatch.setenv("CHALLONGE_SCORE_COMMANDS_ENABLED", "true")
    monkeypatch.delenv("CHALLONGE_DQ_COMMANDS_ENABLED", raising=False)
    provider = ChallongeProvider()
    assert provider.capabilities_v2.for_action("report_forfeit").kind is ProviderActionKind.UNAVAILABLE
