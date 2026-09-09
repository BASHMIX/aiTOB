"""Single idempotent completion boundary for verified provider decisions."""
from __future__ import annotations

from backend.core import database


class CompletionService:
    async def complete(
        self,
        match_id: str,
        *,
        result_kind: str,
        dq_player: str | None = None,
        p1_score: int | None = None,
        p2_score: int | None = None,
    ) -> dict:
        return await database.complete_match_and_enqueue_effects_v2(
            match_id,
            result_kind,
            dq_player=dq_player,
            p1_score=p1_score,
            p2_score=p2_score,
        )
