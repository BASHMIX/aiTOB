"""Durable, testable dispatcher for Hub-local external effects."""
from __future__ import annotations

import json
from uuid import uuid4
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable

from backend.core import database


EffectDispatcher = Callable[[dict], Awaitable[None]]


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
