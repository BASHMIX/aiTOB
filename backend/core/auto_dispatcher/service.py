"""Durable orchestration for deterministic automatic Calls.

This service never contacts a provider or Discord. It delegates the actual Call
to the existing Hub workflow only after a second local-policy evaluation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import replace

from backend.core import database
from backend.core.auto_dispatcher.policy import DispatchDecision, DispatchPolicy
from backend.core.match_state import call_match_core


class AutoDispatcherService:
    def __init__(self, *, policy: DispatchPolicy | None = None,
                 workspace_id: str | None = None):
        self._policy = policy or DispatchPolicy()
        # A live worker is bound to the workspace selected by its durable
        # integration account.  ``None`` remains available only for explicit
        # single-tenant tests/migration tooling; it must not be used by the
        # multi-tenant bot runtime.
        self.workspace_id = workspace_id

    async def run_once(self, *, now: datetime | None = None) -> list[DispatchDecision]:
        """Evaluate every armed event and dispatch only selected local matches."""
        if (await database.get_setting("auto_dispatch_master_switch", "off") or "off").lower() != "on":
            await database.cancel_pending_dispatcher_work()
            return []

        all_decisions: list[DispatchDecision] = []
        for scope in await database.get_dispatch_eligible_events(self.workspace_id):
            event_id = str(scope.get("event_id") or "")
            workspace_id = scope.get("workspace_id")
            tournament = await database.get_tournament(scope["slug"], workspace_id)
            if not tournament:
                continue
            matches = await database.get_active_matches(scope["slug"], event_id, workspace_id)
            verified = await self._verified_entrants(tournament, matches)
            decisions = self._policy.evaluate(
                tournament=tournament,
                event_id=event_id,
                matches=matches,
                verified_entrant_ids=verified,
                now=now or datetime.now(UTC),
            )
            decisions = [replace(item, workspace_id=workspace_id) for item in decisions]
            all_decisions.extend(decisions)
            await self._record(decisions)
            for decision in decisions:
                if decision.decision == "select" and decision.set_id:
                    await self._dispatch_after_recheck(decision, now=now)
        return all_decisions

    async def _verified_entrants(self, tournament: dict, matches: list[dict]) -> set[str]:
        provider = str(tournament.get("provider_type") or "startgg")
        slug = str(tournament["slug"])
        workspace_id = tournament.get("workspace_id")
        entrant_ids = {
            str(match.get(field))
            for match in matches
            for field in ("p1_entrant_id", "p2_entrant_id")
            if match.get(field)
        }
        verified: set[str] = set()
        for entrant_id in entrant_ids:
            link = await database.get_verified_discord_identity_link_v2(provider, slug, entrant_id, workspace_id)
            if link:
                verified.add(entrant_id)
        return verified

    async def _dispatch_after_recheck(self, selected: DispatchDecision, *, now: datetime | None) -> None:
        """Repeat local checks after selection, then call through Hub workflow."""
        # The decision object is intentionally provider-neutral and carries no
        # mutable workspace field. Resolve the trusted owner from the match
        # before rechecking; never let a client-supplied slug select another
        # tenant's tournament.
        workspace_id = selected.workspace_id
        selected_match = await database.get_active_match(selected.set_id, workspace_id)
        # The workspace carried by the durable decision is authoritative.  Do
        # not infer tenant ownership from an unscoped set-id lookup.
        if workspace_id is None:
            workspace_id = (selected_match or {}).get("workspace_id")
        tournament = await database.get_tournament(selected.tournament_slug, workspace_id)
        if not tournament:
            return
        if not bool(tournament.get("auto_dispatch_enabled")):
            await self._record([DispatchDecision(
                selected.tournament_slug, selected.event_id, selected.set_id, "blocked", "policy_disabled",
                "Auto-Dispatcher was disabled for this tournament before the Call started.",
                workspace_id=workspace_id,
            )])
            return
        matches = await database.get_active_matches(selected.tournament_slug, selected.event_id, workspace_id)
        verified = await self._verified_entrants(tournament, matches)
        refreshed = self._policy.evaluate(
            tournament=tournament,
            event_id=selected.event_id,
            matches=matches,
            verified_entrant_ids=verified,
            now=now or datetime.now(UTC),
        )
        refreshed = [replace(item, workspace_id=workspace_id) for item in refreshed]
        recheck = next((item for item in refreshed if item.set_id == selected.set_id), None)
        if not recheck or recheck.decision != "select":
            if recheck:
                await self._record([recheck])
            return
        claim = (await database.claim_dispatcher_match(selected.set_id, selected.tournament_slug, workspace_id)
                 if workspace_id is not None
                 else await database.claim_dispatcher_match(selected.set_id, selected.tournament_slug))
        if not claim:
            await self._record([DispatchDecision(
                selected.tournament_slug, selected.event_id, selected.set_id, "blocked", "dispatch_claimed",
                "Another dispatcher cycle or the Kill Switch prevented this automatic Call.",
                workspace_id=workspace_id,
            )])
            return
        queued = False
        try:
            # Covers either switch changing after selection and before workflow entry.
            claim_active = (await database.dispatcher_claim_is_active(selected.set_id, workspace_id)
                            if workspace_id is not None
                            else await database.dispatcher_claim_is_active(selected.set_id))
            if not claim_active:
                await self._record([DispatchDecision(
                    selected.tournament_slug, selected.event_id, selected.set_id, "blocked", "dispatch_stopped",
                    "The tournament dispatcher or global Kill Switch was turned off before the Call started.",
                    workspace_id=workspace_id,
                )])
                return
            result = await call_match_core(
                selected.set_id, source="dispatcher", workspace_id=workspace_id,
            )
            if result.get("error"):
                await self._record([DispatchDecision(
                    selected.tournament_slug, selected.event_id, selected.set_id, "blocked", "call_rejected",
                    f"The Hub workflow rejected the automatic Call: {result['error']}",
                    workspace_id=workspace_id,
                )])
                return
            if workspace_id is not None:
                await database.mark_dispatcher_claim_queued(selected.set_id, workspace_id)
            else:
                await database.mark_dispatcher_claim_queued(selected.set_id)
            queued = True
        finally:
            # A failed/prevented call may be evaluated again; a queued call keeps
            # its durable claim until the Kill Switch cancels pending work.
            if not queued:
                if workspace_id is not None:
                    await database.release_dispatcher_claim(selected.set_id, workspace_id)
                else:
                    await database.release_dispatcher_claim(selected.set_id)

    @staticmethod
    async def _record(decisions: list[DispatchDecision]) -> None:
        for decision in decisions:
            await database.record_dispatcher_decision(
                decision_key=decision.decision_key,
                tournament_slug=decision.tournament_slug,
                event_id=decision.event_id,
                set_id=decision.set_id,
                decision=decision.decision,
                reason_code=decision.reason_code,
                explanation=decision.explanation,
                workspace_id=decision.workspace_id,
            )
