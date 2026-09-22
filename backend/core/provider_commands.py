"""Durable provider-command dispatch and unknown-outcome recovery."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable, Protocol, TypeVar
from uuid import uuid4

from backend.core import database


T = TypeVar("T")


class DurableProviderMutationService:
    """Persist a mutation intent before invoking an adapter exactly once.

    A transport exception or an existing acknowledged command is never resent.
    Provider-specific reconciliation remains with the caller/coordinator.
    """

    def __init__(self, *, workspace_id: str):
        if not str(workspace_id or "").strip():
            raise ValueError("Provider mutation requires a workspace")
        self.workspace_id = str(workspace_id)

    async def dispatch(
        self,
        *,
        match_id: str,
        action: str,
        payload: dict,
        operation: Callable[[], Awaitable[T]],
        expected_result: dict | None = None,
        precondition_revision: str | None = None,
    ) -> T:
        from backend.core.match_commands import MatchCommandError, ProviderCommandLifecycle

        lifecycle = ProviderCommandLifecycle(workspace_id=self.workspace_id)
        command = await lifecycle.create_remote_command(
            match_id=match_id,
            action=action,
            payload=payload,
            expected_result=expected_result or {},
            precondition_revision=precondition_revision,
        )
        state = str(command.get("state") or "pending")
        if state in {"acknowledged", "sending", "retryable"}:
            raise MatchCommandError(
                "Provider command outcome is awaiting reconciliation; it was not resent"
            )
        if state == "snapshot_verified":
            raise MatchCommandError("Provider command was already completed")
        if state in {"permanent_failure", "conflict", "needs_review"}:
            raise MatchCommandError("Provider command requires organizer review")

        await lifecycle.mark(command["id"], "sending")
        try:
            result = await operation()
        except Exception:
            await lifecycle.mark(
                command["id"], "acknowledged",
                reason="Remote outcome unknown; verification required",
            )
            await database.set_match_sync_status_v2(
                match_id,
                "acknowledged_unverified",
                reason="Remote outcome unknown; awaiting verification",
                workspace_id=self.workspace_id,
            )
            raise

        success = bool(getattr(result, "success", True))
        if success:
            await lifecycle.mark(command["id"], "acknowledged")
        else:
            await lifecycle.mark(
                command["id"], "permanent_failure",
                reason=str(getattr(result, "error_message", "Provider rejected command")),
            )
        return result

    async def dispatch_tournament(
        self,
        *,
        tournament: dict,
        action: str,
        payload: dict,
        operation: Callable[[], Awaitable[T]],
        expected_result: dict | None = None,
    ) -> tuple[T, str]:
        """Persist a tournament-level mutation before contacting the provider."""
        from backend.core.match_commands import MatchCommandError

        slug = str(tournament.get("slug") or "")
        account_id = str(tournament.get("provider_account_id") or "")
        provider_type = str(tournament.get("provider_type") or "startgg")
        if not slug or not account_id or str(tournament.get("workspace_id") or "") != self.workspace_id:
            raise MatchCommandError("Tournament provider binding is incomplete")

        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        resource_id = f"tournament:{slug}"
        command = await database.get_open_provider_command_for_match_v2(
            resource_id, action, self.workspace_id
        )
        if command and command.get("payload_digest") != digest:
            raise MatchCommandError(
                "A different tournament command is awaiting provider reconciliation"
            )
        if command is None:
            command = await database.create_provider_command_v2({
                "id": str(uuid4()),
                "workspace_id": self.workspace_id,
                "tournament_slug": slug,
                "set_id": resource_id,
                "provider_type": provider_type,
                "provider_account_id": account_id,
                "action": action,
                "idempotency_key": f"{action}:{resource_id}:{digest}",
                "payload_digest": digest,
                "expected_result": expected_result or {},
            })

        state = str(command.get("state") or "pending")
        if state in {"acknowledged", "sending", "retryable"}:
            raise MatchCommandError(
                "Tournament command outcome is awaiting reconciliation; it was not resent"
            )
        if state == "snapshot_verified":
            raise MatchCommandError("Tournament command was already completed")
        if state in {"permanent_failure", "conflict", "needs_review"}:
            raise MatchCommandError("Tournament command requires organizer review")

        await database.update_provider_command_state_v2(command["id"], "sending")
        try:
            result = await operation()
        except Exception:
            await database.update_provider_command_state_v2(
                command["id"], "acknowledged",
                reason="Remote outcome unknown; snapshot verification required",
            )
            raise
        if bool(getattr(result, "success", True)):
            await database.update_provider_command_state_v2(command["id"], "acknowledged")
        else:
            await database.update_provider_command_state_v2(
                command["id"], "permanent_failure",
                reason=str(getattr(result, "error_message", "Provider rejected command")),
            )
        return result, str(command["id"])


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
