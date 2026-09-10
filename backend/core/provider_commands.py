"""Dark provider-command interfaces.

These definitions model remote mutations only.  Local Hub workflow actions such as
Call, Ready, station assignment, Discord, and OBS remain on their current paths in
Phase 2 and must not create provider-command records.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable, Protocol
from uuid import uuid4

from backend.core import database


@dataclass(frozen=True)
class ProviderCommandLease:
    command_id: str
    lease_until: str
    attempt_count: int


class ProviderCommandStore(Protocol):
    """Persistence boundary for a later flag-gated command worker."""

    async def create_remote_command(self, command: dict) -> dict: ...

    async def claim_due_remote_commands(
        self, now: str, lease_until: str, *, limit: int = 20
    ) -> list[dict]: ...


class WorkflowOutboxStore(Protocol):
    """Persistence boundary for a later Discord/OBS dispatcher."""

    async def enqueue_local_effect(self, event: dict) -> dict: ...

    async def claim_due_local_effects(self, now: str, *, limit: int = 20) -> list[dict]: ...


CommandVerifier = Callable[[dict], Awaitable[None]]
VerificationAttempt = Callable[[], Awaitable[bool]]


class ResultVerificationBackoff:
    """Fast targeted verification separate from the coarse Live scheduler.

    Each attempt must be a read-only verification. The object contains no
    provider mutation callback, so a timeout can never turn into a resend.
    """

    CHECKPOINTS_SECONDS = (5, 15, 30, 60)

    def __init__(self, attempt: VerificationAttempt, *, sleep: Callable[[float], Awaitable[None]]):
        self._attempt = attempt
        self._sleep = sleep

    async def run(self) -> bool:
        previous_checkpoint = 0
        for checkpoint in self.CHECKPOINTS_SECONDS:
            # `sleep` receives the interval since the prior checkpoint, so
            # attempts occur at 5/15/30/60 seconds from acknowledgement rather
            # than the accidental cumulative 5/20/50/110 schedule.
            delay = checkpoint - previous_checkpoint
            await self._sleep(delay)
            if await self._attempt():
                return True
            previous_checkpoint = checkpoint
        return False


class ProviderCommandRecoveryWorker:
    """Recover leases for verification work, never blindly re-send mutations.

    A command whose request outcome is ambiguous is handed to the verifier. The
    verifier may fetch a snapshot and decide verified/conflict/retry; it is not
    authorized to repeat a provider mutation merely because a lease expired.
    """

    def __init__(self, verify: CommandVerifier, *, lease_seconds: int = 60,
                 lease_owner: str | None = None, workspace_id: str | None = None):
        self._verify = verify
        self._lease_seconds = lease_seconds
        self.lease_owner = lease_owner or f"command:{uuid4()}"
        self.workspace_id = workspace_id

    async def run_once(self, *, now: str | None = None, limit: int = 20) -> int:
        instant = now or datetime.now(UTC).isoformat()
        lease_until = (
            datetime.fromisoformat(instant.replace("Z", "+00:00"))
            + timedelta(seconds=self._lease_seconds)
        ).isoformat()
        commands = await database.claim_due_provider_commands_v2(
            instant, lease_until, limit=limit, lease_owner=self.lease_owner,
            workspace_id=self.workspace_id,
        )
        recovered = 0
        for command in commands:
            # Check the durable state again after acquiring: another actor may
            # have completed it before this context got CPU time.
            current = await database.get_provider_command_v2(command["id"])
            if not current or current.get("state") != "sending" or current.get("lease_owner") != self.lease_owner:
                continue
            await self._verify(current)
            recovered += 1
        return recovered
