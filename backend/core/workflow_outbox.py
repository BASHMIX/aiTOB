"""Durable, testable dispatcher for Hub-local external effects."""
from __future__ import annotations

import json
from uuid import uuid4
from datetime import UTC, datetime, timedelta
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import quote

from backend.core import database


EffectDispatcher = Callable[[dict], Awaitable[None]]


# These keys are intentionally constructed here rather than by individual
# callers.  All external effects therefore use the same workspace boundary and
# the same escaping rules.  The source of a CALL transition is deliberately not
# part of the call-occurrence key: provider sync and an authorized Dashboard
# action must converge on one Discord delivery for the same occurrence.
_KEY_VERSION = "v1"


def _key_component(value: object, *, name: str) -> str:
    """Return one unambiguous, non-secret idempotency-key component.

    IDs may be provider supplied and can contain ``:``, ``/`` or ``@``.  URL
    quoting keeps those values from changing the meaning of neighbouring key
    components.  Empty values are rejected so a missing workspace cannot turn
    into a process-global key.
    """

    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} is required for an outbox idempotency key.")
    component = str(value).strip()
    if not component:
        raise ValueError(f"{name} is required for an outbox idempotency key.")
    return quote(component, safe="")


def _version_component(value: object, *, name: str) -> str:
    """Normalize a schedule/occurrence version while allowing integer zero."""

    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} is required for an outbox idempotency key.")
    component = str(value).strip()
    if not component:
        raise ValueError(f"{name} is required for an outbox idempotency key.")
    return quote(component, safe="")


def _effect_key(namespace: str, *components: object) -> str:
    return ":".join(
        [_key_component("aitob", name="namespace"), _key_component(_KEY_VERSION, name="version"),
         _key_component(namespace, name="effect type"), *components]
    )


def registration_job_idempotency_key(
    workspace_id: object,
    tournament_id: object,
    operation: object,
    schedule_version: object,
    *,
    target_id: object | None = None,
) -> str:
    """Build a key for one tournament registration job.

    ``schedule_version`` changes whenever the organizer edits the registration
    schedule.  A stale open/close/reminder job consequently cannot publish a
    superseded registration action.  ``target_id`` is optional for jobs that
    target the whole tournament and can identify one enrollment/role update.
    """

    components = [
        _key_component(workspace_id, name="workspace_id"),
        _key_component(tournament_id, name="tournament_id"),
        _key_component(operation, name="operation"),
        _version_component(schedule_version, name="schedule_version"),
    ]
    if target_id is not None:
        components.extend(["target", _key_component(target_id, name="target_id")])
    return _effect_key("registration", *components)


def initial_sync_idempotency_key(
    workspace_id: object,
    tournament_id: object,
    activation_version: object = "1",
) -> str:
    """Build the durable key for activation's initial provider synchronization."""

    return _effect_key(
        "initial-sync",
        _key_component(workspace_id, name="workspace_id"),
        _key_component(tournament_id, name="tournament_id"),
        _version_component(activation_version, name="activation_version"),
    )


def provider_start_idempotency_key(
    workspace_id: object,
    tournament_id: object,
    provider_type: object,
    provider_tournament_id: object,
    *,
    attempt_version: object = "1",
    provider_account_id: object | None = None,
) -> str:
    """Build a key for one explicitly confirmed remote bracket-start attempt."""

    components = [
        _key_component(workspace_id, name="workspace_id"),
        _key_component(tournament_id, name="tournament_id"),
        _key_component(provider_type, name="provider_type"),
        _key_component(provider_tournament_id, name="provider_tournament_id"),
        _version_component(attempt_version, name="attempt_version"),
    ]
    if provider_account_id is not None:
        components.extend(["account", _key_component(provider_account_id, name="provider_account_id")])
    return _effect_key("provider-start", *components)


def call_occurrence_idempotency_key(
    workspace_id: object,
    tournament_id: object,
    match_id: object,
    occurrence_version: object,
) -> str:
    """Build the shared provider/Dashboard ``CALLED`` delivery key.

    Do not add an origin/source argument here.  ``provider_sync`` and
    ``dashboard`` are observations of the same occurrence and must deduplicate
    to one outbox row.
    """

    return _effect_key(
        "call-occurrence",
        _key_component(workspace_id, name="workspace_id"),
        _key_component(tournament_id, name="tournament_id"),
        _key_component(match_id, name="match_id"),
        _version_component(occurrence_version, name="occurrence_version"),
    )


# Short aliases keep call sites readable while the explicit names remain useful
# in tests and code search.
registration_job_key = registration_job_idempotency_key
initial_sync_key = initial_sync_idempotency_key
provider_start_key = provider_start_idempotency_key
call_occurrence_key = call_occurrence_idempotency_key


def _tournament_target(tournament_id: object) -> str:
    """Map a tournament-scoped effect to the legacy outbox match_id column."""

    return f"tournament:{_key_component(tournament_id, name='tournament_id')}"


def build_registration_job_event(
    *,
    event_id: str | None = None,
    workspace_id: object,
    tournament_id: object,
    operation: object,
    schedule_version: object,
    target_id: object | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an outbox event ready for ``enqueue_workflow_outbox_v2``."""

    # Validate once here; pass the original value to the key builder so it is
    # escaped exactly once (``%`` from URL quoting must not be double encoded).
    _version_component(schedule_version, name="schedule_version")
    event_payload = dict(payload or {})
    event_payload.update({
        "workspace_id": str(workspace_id).strip(),
        "tournament_id": str(tournament_id).strip(),
        "operation": str(operation).strip(),
        "schedule_version": str(schedule_version).strip(),
    })
    if target_id is not None:
        event_payload["target_id"] = str(target_id).strip()
    return {
        "event_id": event_id or str(uuid4()),
        "match_id": _tournament_target(tournament_id),
        "event_type": "registration_job",
        "deduplication_key": registration_job_idempotency_key(
            workspace_id, tournament_id, operation, schedule_version, target_id=target_id
        ),
        "payload": event_payload,
        "workspace_id": str(workspace_id).strip(),
    }


def build_initial_sync_event(
    *,
    event_id: str | None = None,
    workspace_id: object,
    tournament_id: object,
    activation_version: object = "1",
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the post-activation initial-sync outbox event."""

    event_payload = dict(payload or {})
    event_payload.update({
        "workspace_id": str(workspace_id).strip(),
        "tournament_id": str(tournament_id).strip(),
        "activation_version": str(activation_version).strip(),
    })
    return {
        "event_id": event_id or str(uuid4()),
        "match_id": _tournament_target(tournament_id),
        "event_type": "initial_sync",
        "deduplication_key": initial_sync_idempotency_key(workspace_id, tournament_id, activation_version),
        "payload": event_payload,
        "workspace_id": str(workspace_id).strip(),
    }


def build_provider_start_event(
    *,
    event_id: str | None = None,
    workspace_id: object,
    tournament_id: object,
    provider_type: object,
    provider_tournament_id: object,
    attempt_version: object = "1",
    provider_account_id: object | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an explicitly confirmed remote provider-start event."""

    event_payload = dict(payload or {})
    event_payload.update({
        "workspace_id": str(workspace_id).strip(),
        "tournament_id": str(tournament_id).strip(),
        "provider_type": str(provider_type).strip(),
        "provider_tournament_id": str(provider_tournament_id).strip(),
        "attempt_version": str(attempt_version).strip(),
    })
    if provider_account_id is not None:
        event_payload["provider_account_id"] = str(provider_account_id).strip()
    return {
        "event_id": event_id or str(uuid4()),
        "match_id": _tournament_target(tournament_id),
        "event_type": "provider_start",
        "deduplication_key": provider_start_idempotency_key(
            workspace_id, tournament_id, provider_type, provider_tournament_id,
            attempt_version=attempt_version, provider_account_id=provider_account_id,
        ),
        "payload": event_payload,
        "workspace_id": str(workspace_id).strip(),
    }


def build_call_occurrence_event(
    *,
    event_id: str | None = None,
    workspace_id: object,
    tournament_id: object,
    match_id: object,
    occurrence_version: object,
    source_first_observed: object,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one Discord call event shared by provider and Dashboard sources."""

    event_payload = dict(payload or {})
    event_payload.update({
        "workspace_id": str(workspace_id).strip(),
        "tournament_id": str(tournament_id).strip(),
        "match_id": str(match_id).strip(),
        "occurrence_version": str(occurrence_version).strip(),
        "source_first_observed": str(source_first_observed).strip(),
    })
    return {
        "event_id": event_id or str(uuid4()),
        "match_id": str(match_id).strip(),
        "event_type": "discord_call",
        "deduplication_key": call_occurrence_idempotency_key(
            workspace_id, tournament_id, match_id, occurrence_version
        ),
        "payload": event_payload,
        "workspace_id": str(workspace_id).strip(),
    }


class ExternalEffectUnknown(RuntimeError):
    """The receiver may have accepted an effect but did not prove the outcome.

    A lease only prevents two local workers from starting concurrently; it
    cannot prove a Discord/provider receiver did not act before a timeout.
    Such a record must be reconciled or reviewed, never blindly retried.
    """


class ExternalEffectNotSent(RuntimeError):
    """Adapter proved no external effect occurred; retry is explicitly safe."""


class WorkflowOutboxWorker:
    """Dispatch claimed effects once; failures remain durable retryable records."""

    def __init__(self, dispatch: EffectDispatcher, *, lease_seconds: int = 60,
                 lease_owner: str | None = None, workspace_id: str | None = None):
        self._dispatch = dispatch
        self._lease_seconds = lease_seconds
        self.lease_owner = lease_owner or f"outbox:{uuid4()}"
        self.workspace_id = workspace_id

    async def run_once(self, *, now: str | None = None, limit: int = 20) -> int:
        instant = now or datetime.now(UTC).isoformat()
        lease = (datetime.fromisoformat(instant.replace("Z", "+00:00")) + timedelta(seconds=self._lease_seconds)).isoformat()
        events = await database.claim_due_workflow_outbox_v2(
            instant, lease, limit=limit, lease_owner=self.lease_owner,
            workspace_id=self.workspace_id,
        )
        completed = 0
        for event in events:
            if not await database.begin_workflow_outbox_effect_v2(
                event["event_id"], self.lease_owner,
                instant if now is not None else datetime.now(UTC).isoformat(),
            ):
                continue
            try:
                event["payload"] = json.loads(event.pop("payload_json") or "{}")
                await self._dispatch(event)
            except ExternalEffectNotSent:
                await database.mark_workflow_outbox_retryable_v2(
                    event["event_id"], "receiver_not_contacted", lease_owner=self.lease_owner
                )
            except Exception:
                await database.mark_workflow_outbox_needs_review_v2(
                    event["event_id"], "external_outcome_unknown", lease_owner=self.lease_owner
                )
            else:
                completed += int(await database.mark_workflow_outbox_completed_v2(
                    event["event_id"], lease_owner=self.lease_owner
                ))
        return completed
