"""Pure selection policy for automatic match calls.

No database, provider, Discord, station, or queue writes belong in this module.
Its output is intentionally auditable and can be tested from a fixed snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable


DISPATCH_FRESHNESS_SECONDS = 120
TERMINAL_STATUSES = {"complete", "dq", "cancelled", "void"}


@dataclass(frozen=True)
class DispatchDecision:
    tournament_slug: str
    event_id: str
    set_id: str | None
    decision: str
    reason_code: str
    explanation: str
    workspace_id: str | None = None

    @property
    def decision_key(self) -> str:
        return ":".join((
            self.workspace_id or "legacy",
            self.tournament_slug,
            self.event_id or "default",
            self.set_id or "scope",
            self.decision,
            self.reason_code,
        ))


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        return None


def _is_fresh(match: dict, tournament: dict, now: datetime, ttl_seconds: int) -> bool:
    observed = (
        match.get("last_successful_snapshot_at")
        or match.get("provider_observed_at")
        or tournament.get("provider_last_synced_at")
    )
    timestamp = _parse_timestamp(observed)
    if timestamp is None:
        return False
    return (now - timestamp).total_seconds() <= ttl_seconds


def _is_tbd(match: dict) -> bool:
    names = (str(match.get("p1_name") or ""), str(match.get("p2_name") or ""))
    entrant_ids = (match.get("p1_entrant_id"), match.get("p2_entrant_id"))
    return not all(entrant_ids) or any(not name or name.strip().lower() == "tbd" for name in names)


def _is_bye(match: dict) -> bool:
    return any(str(match.get(field) or "").strip().lower() == "bye" for field in ("p1_name", "p2_name"))


class DispatchPolicy:
    """Evaluate one event's durable local snapshot into select/skip decisions."""

    def __init__(self, *, freshness_seconds: int = DISPATCH_FRESHNESS_SECONDS):
        self.freshness_seconds = freshness_seconds

    def evaluate(
        self,
        *,
        tournament: dict,
        event_id: str,
        matches: Iterable[dict],
        verified_entrant_ids: set[str],
        now: datetime | None = None,
    ) -> list[DispatchDecision]:
        current_time = now or datetime.now(UTC)
        event = event_id or ""
        rows = list(matches)
        slug = str(tournament["slug"])
        concurrency = max(1, int(tournament.get("auto_dispatch_concurrency") or 1))
        stop_at = max(0, int(tournament.get("auto_dispatch_stop_at") if tournament.get("auto_dispatch_stop_at") is not None else 8))
        remaining = sum(str(row.get("status") or "not_started") not in TERMINAL_STATUSES for row in rows)
        active = sum(
            str(row.get("status") or "") in {"called", "ready", "in_progress"}
            and bool(row.get("bot_enabled", True))
            for row in rows
        )

        if remaining <= stop_at:
            return [DispatchDecision(
                slug, event, None, "skip", "handoff_threshold",
                f"{remaining} unfinished match(es) remain; the organizer handoff threshold is {stop_at}.",
            )]
        if active >= concurrency:
            return [DispatchDecision(
                slug, event, None, "skip", "concurrency_reached",
                f"{active} bot-managed match(es) are active; this event limit is {concurrency}.",
            )]

        slots = concurrency - active
        decisions: list[DispatchDecision] = []
        allow_on_stream = bool(tournament.get("auto_dispatch_on_stream", False))
        candidates = sorted(
            (row for row in rows if str(row.get("status") or "not_started") == "not_started"),
            key=lambda row: (
                str(row.get("phase_group") or "zzzz"),
                int(row.get("match_number") or 999999),
                str(row.get("created_at") or ""),
            ),
        )
        selected = 0
        for match in candidates:
            set_id = str(match["set_id"])
            if not bool(match.get("bot_enabled", True)):
                decisions.append(DispatchDecision(slug, event, set_id, "skip", "bot_disabled", "Bot management is disabled for this match."))
                continue
            if _is_bye(match):
                decisions.append(DispatchDecision(slug, event, set_id, "skip", "bye", "A bye is not a callable head-to-head match."))
                continue
            if _is_tbd(match):
                decisions.append(DispatchDecision(slug, event, set_id, "skip", "unresolved_bracket", "Both bracket sides must be resolved before an automatic Call."))
                continue
            if bool(match.get("is_stream_match")) and not allow_on_stream:
                decisions.append(DispatchDecision(slug, event, set_id, "skip", "on_stream_excluded", "On-stream matches require an explicit organizer Call by default."))
                continue
            if not _is_fresh(match, tournament, current_time, self.freshness_seconds):
                decisions.append(DispatchDecision(slug, event, set_id, "skip", "stale_snapshot", "The local provider snapshot is older than the dispatcher freshness limit."))
                continue
            entrants = {str(match.get("p1_entrant_id")), str(match.get("p2_entrant_id"))}
            if not entrants.issubset(verified_entrant_ids):
                decisions.append(DispatchDecision(slug, event, set_id, "skip", "identity_unverified", "Both bracket entrants need a verified Discord identity link."))
                continue
            if selected >= slots:
                decisions.append(DispatchDecision(slug, event, set_id, "skip", "concurrency_reached", "The event reached its available dispatch slots in this cycle."))
                continue
            decisions.append(DispatchDecision(slug, event, set_id, "select", "eligible", "Eligible local match selected by deterministic event order."))
            selected += 1
        return decisions
