"""Provider-safe per-entrant attendance commands."""
from __future__ import annotations

from backend.core import database


class AttendanceCommandError(ValueError):
    """Organizer-facing refusal for an invalid attendance transition."""


class AttendanceCommandService:
    """Record attendance without fabricating a bracket result.

    The same service is intended for authorized manual controls and verified
    Discord self-service.  Start.gg owns the called-window deadline and final
    single-/double-DQ outcome; aiTOB only records the entrant intent here.
    """

    def __init__(self, *, workspace_id: str | None = None):
        self.workspace_id = workspace_id

    async def set_attendance(
        self,
        match_id: str,
        *,
        player: str,
        state: str,
        source: str,
    ) -> dict:
        try:
            match = await database.record_startgg_attendance_intent_v2(
                match_id,
                player,
                state,
                source=source,
                workspace_id=self.workspace_id,
            )
        except ValueError as exc:
            raise AttendanceCommandError(str(exc)) from exc
        return {"outcome": "local_intent_recorded", "match": match}
