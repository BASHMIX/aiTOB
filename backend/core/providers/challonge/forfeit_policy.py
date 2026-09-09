"""Challonge single-player forfeit policy.

Challonge represents a forfeit publicly as ``0 / -1`` rather than a native DQ
badge.  aiTOB therefore requires an explicit provider flag before dispatching
it, but does support a single disqualified player.  A double DQ stays
unrepresentable: an elimination bracket needs one real advancing entrant.
"""
from __future__ import annotations

from dataclasses import dataclass


class ForfeitUnsupported(ValueError):
    pass


@dataclass(frozen=True)
class ForfeitCandidate:
    winner_id: str
    entrant1_id: str
    entrant2_id: str

    def attributes(self) -> dict:
        return {
            "match": [
                {
                    "participant_id": self.entrant1_id,
                    "score_set": "0" if self.winner_id == self.entrant1_id else "-1",
                    "advancing": self.winner_id == self.entrant1_id,
                },
                {
                    "participant_id": self.entrant2_id,
                    "score_set": "0" if self.winner_id == self.entrant2_id else "-1",
                    "advancing": self.winner_id == self.entrant2_id,
                },
            ],
        }


class ForfeitPolicy:
    """Produces the public ``0/-1`` representation for one forfeit."""

    SANDBOX_PROOF_RECORDED = True

    @classmethod
    def availability_reason(cls) -> str:
        return "Challonge single-player DQ is disabled. When enabled it is sent as 0/-1 and the other player advances."

    @classmethod
    def candidate(cls, *, winner_id: str, entrant1_id: str, entrant2_id: str) -> ForfeitCandidate:
        if not entrant1_id or not entrant2_id or winner_id not in {entrant1_id, entrant2_id}:
            raise ForfeitUnsupported("A single verified winner and two entrant IDs are required for a forfeit candidate.")
        return ForfeitCandidate(
            winner_id=winner_id,
            entrant1_id=entrant1_id,
            entrant2_id=entrant2_id,
        )

    @classmethod
    def require_dispatchable(cls) -> None:
        if not cls.SANDBOX_PROOF_RECORDED:
            raise ForfeitUnsupported(cls.availability_reason())
