"""Restart-safe recovery for durable Hub workflow state."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Awaitable, Callable

from backend.core import database


def _utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp.astimezone(UTC) if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class RecoveryReport:
    restored_matches: tuple[str, ...]
    future_deadlines: tuple[str, ...]
    overdue_deadlines: tuple[str, ...]
    skipped_terminal: tuple[str, ...]


class AttendanceTimerService:
    """Schedules durable future deadlines; expiry requests review and never DQs."""

    def __init__(self, *, now: Callable[[], datetime] | None = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self._tasks: dict[str, asyncio.Task] = {}

    def restore(self, match: dict) -> str:
        match_id = str(match["set_id"])
        deadline = _utc(match.get("attendance_deadline"))
        if not deadline:
            return "none"
        if match.get("hub_status") == "complete" or match.get("provider_state_normalized") == "complete":
            self.cancel(match_id)
            return "terminal"
        remaining = (deadline - self._now()).total_seconds()
        if remaining <= 0:
            return "overdue_review"
        self.cancel(match_id)
        self._tasks[match_id] = asyncio.create_task(
            self._wait(match_id, remaining, str(match.get("workspace_id") or "") or None)
        )
        return "scheduled"

    async def _wait(self, match_id: str, seconds: float, workspace_id: str | None = None) -> None:
        try:
            await self._sleep(seconds)
            current = await database.get_active_match(match_id, workspace_id)
            if not current or current.get("hub_status") == "complete" or current.get("provider_state_normalized") == "complete":
                return
            await database.set_match_sync_status_v2(
                match_id, "needs_review", workspace_id=workspace_id,
                reason="Attendance deadline elapsed while recovery was active",
            )
            await database.enqueue_workflow_outbox_v2({
                "event_id": f"attendance-review:{match_id}", "match_id": match_id,
                "event_type": "attendance_deadline_review",
                "deduplication_key": f"attendance_deadline_review:{match_id}",
                "workspace_id": workspace_id,
                "payload": {"match_id": match_id},
            })
        finally:
            self._tasks.pop(match_id, None)

    def cancel(self, match_id: str) -> None:
        task = self._tasks.pop(match_id, None)
        if task and not task.done():
            task.cancel()

    async def close(self) -> None:
        for match_id in tuple(self._tasks):
            self.cancel(match_id)
        await asyncio.sleep(0)


class RecoveryService:
    """Build a fresh restart plan from SQLite, with no in-memory carry-over."""

    def __init__(self, *, timers: AttendanceTimerService | None = None):
        self.timers = timers or AttendanceTimerService()

    async def restore(self) -> RecoveryReport:
        restored: list[str] = []
        future: list[str] = []
        overdue: list[str] = []
        terminal: list[str] = []
        for match in await database.list_recovery_matches_v2():
            match_id = str(match["set_id"])
            restored.append(match_id)
            result = self.timers.restore(match)
            if result == "scheduled":
                future.append(match_id)
            elif result == "overdue_review":
                await database.set_match_sync_status_v2(
                    match_id, "needs_review", workspace_id=match.get("workspace_id"),
                    reason="Attendance deadline elapsed while aiTOB was offline",
                )
                overdue.append(match_id)
            elif result == "terminal":
                terminal.append(match_id)
        return RecoveryReport(tuple(restored), tuple(future), tuple(overdue), tuple(terminal))

    async def close(self) -> None:
        await self.timers.close()
