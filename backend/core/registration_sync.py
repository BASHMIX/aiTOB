"""Exact provider-roster synchronization for tournament registration.

The synchronizer accepts an already-fetched roster so provider I/O stays outside
the database transaction.  It persists only the selected workspace,
tournament, and Event/bracket scope, writes a deterministic snapshot, updates
existing enrollments idempotently, and marks removed entrants for review while
retaining their Discord identity and image.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import UTC, datetime
import hashlib
import json
import uuid
from typing import Any, Awaitable, Callable, Iterable, Mapping

from backend.core import database
from backend.core.player_registration import RegistrationError
from backend.core.registration_identity import detect_gamertag_collisions
from backend.core.storage import dbapi as aiosqlite, is_postgres


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _value(entrant: Mapping[str, Any] | Any, *names: str) -> Any:
    for name in names:
        if isinstance(entrant, Mapping):
            value = entrant.get(name)
        else:
            value = getattr(entrant, name, None)
        if value is not None and str(value).strip():
            return value
    return None


def canonical_entrant(entrant: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Project one provider entrant into safe canonical registration fields."""

    entrant_id = _text(_value(entrant, "provider_entrant_id", "entrant_id", "id"))
    if not entrant_id:
        raise RegistrationError("provider_entrant_id_required")
    display_name = _text(_value(entrant, "display_name", "name")) or f"Entrant {entrant_id}"
    gamertag = _text(_value(entrant, "gamertag", "gamer_tag", "gamerTag")) or display_name
    return {
        "provider_entrant_id": entrant_id,
        "provider_user_id": _text(_value(entrant, "provider_user_id", "user_id", "player_id")),
        "prefix": _text(_value(entrant, "prefix", "team", "clan")),
        "gamertag": gamertag,
        "display_name": display_name,
    }


def _canonical_roster(entrants: Iterable[Mapping[str, Any] | Any]) -> list[dict[str, Any]]:
    # Duplicate entrant IDs are contradictory provider evidence.  Keep the
    # first deterministic record and let the caller's collision/review path
    # handle duplicate names; never silently overwrite one player with another.
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in entrants:
        value = canonical_entrant(item)
        if value["provider_entrant_id"] in seen:
            continue
        seen.add(value["provider_entrant_id"])
        result.append(value)
    return result


def roster_fingerprint(entrants: Iterable[Mapping[str, Any] | Any]) -> str:
    """Hash sorted stable entrant IDs; name changes remain a new enrollment diff."""

    values = _canonical_roster(entrants)
    encoded = "\n".join(sorted(item["provider_entrant_id"] for item in values)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RosterSyncResult:
    snapshot_id: str
    provider_type: str
    tournament_id: str
    external_scope_id: str
    provider_revision: str | None
    observed_at: str
    added: int
    updated: int
    unchanged: int
    removed: int
    collision_count: int
    affected_enrollment_ids: tuple[str, ...] = ()
    status: str = "synced"
    error_code: str | None = None

    @property
    def counts(self) -> dict[str, int]:
        return {
            "total": self.added + self.updated + self.unchanged,
            "added": self.added,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "removed": self.removed,
            "collisions": self.collision_count,
        }

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["affected_enrollment_ids"] = list(self.affected_enrollment_ids)
        result["counts"] = self.counts
        return result


async def sync_provider_roster(
    tournament_id: str,
    workspace_id: str,
    *,
    provider_type: str,
    provider_account_id: str,
    external_scope_id: str,
    entrants: Iterable[Mapping[str, Any] | Any],
    provider_revision: str | None = None,
    observed_at: str | None = None,
) -> RosterSyncResult:
    """Synchronize one exact Event/bracket roster idempotently."""

    if not tournament_id or not workspace_id or not external_scope_id:
        raise RegistrationError("registration_scope_required")
    provider_type = str(provider_type or "").strip().lower()
    if provider_type not in {"startgg", "challonge"}:
        raise RegistrationError("unsupported_registration_provider")
    if not provider_account_id:
        raise RegistrationError("provider_account_required")
    roster = _canonical_roster(entrants)
    observed = str(observed_at or _now())
    fingerprint = roster_fingerprint(roster)
    collisions = detect_gamertag_collisions(roster)
    collision_ids = {entrant_id for collision in collisions for entrant_id in collision.entrant_ids}
    affected: list[str] = []
    added = updated = unchanged = removed = 0

    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            snapshot = await (await db.execute(
                "SELECT id FROM provider_roster_snapshots WHERE workspace_id=? AND tournament_id=? AND external_scope_id=? AND entrant_fingerprint=?",
                (workspace_id, tournament_id, external_scope_id, fingerprint),
            )).fetchone()
            snapshot_id = str(snapshot[0]) if snapshot else str(uuid.uuid4())
            if not snapshot:
                await db.execute(
                    """INSERT INTO provider_roster_snapshots
                       (id, workspace_id, tournament_id, provider_account_id, external_scope_id,
                        provider_revision, entrant_fingerprint, observed_at, safe_counts_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (snapshot_id, workspace_id, tournament_id, provider_account_id,
                     external_scope_id, provider_revision, fingerprint, observed,
                     json.dumps({"total": len(roster), "collisions": len(collisions)}, separators=(",", ":"))),
                )
            else:
                await db.execute(
                    """UPDATE provider_roster_snapshots
                       SET provider_account_id=?, provider_revision=?, observed_at=?, safe_counts_json=?
                       WHERE id=? AND workspace_id=? AND tournament_id=? AND external_scope_id=?""",
                    (provider_account_id, provider_revision, observed,
                     json.dumps({"total": len(roster), "collisions": len(collisions)}, separators=(",", ":")),
                     snapshot_id, workspace_id, tournament_id, external_scope_id),
                )

            current_ids = {item["provider_entrant_id"] for item in roster}
            lock = " FOR UPDATE" if is_postgres() else ""
            old_rows = await (await db.execute(
                """SELECT e.* FROM tournament_player_enrollments e
                   JOIN provider_roster_snapshots s ON s.id=e.roster_snapshot_id
                    AND s.workspace_id=e.workspace_id AND s.tournament_id=e.tournament_id
                   WHERE e.workspace_id=? AND e.tournament_id=? AND e.provider_entrant_id IS NOT NULL
                     AND s.external_scope_id=?""" + lock,
                (workspace_id, tournament_id, external_scope_id),
            )).fetchall()
            by_entrant = {str(row["provider_entrant_id"]): row for row in old_rows}
            for item in roster:
                old = by_entrant.get(item["provider_entrant_id"])
                if old is None:
                    enrollment_id = str(uuid.uuid4())
                    state = "needs_review" if item["provider_entrant_id"] in collision_ids else "awaiting_discord_link"
                    reason = "gamertag_collision" if item["provider_entrant_id"] in collision_ids else None
                    await db.execute(
                        """INSERT INTO tournament_player_enrollments
                           (id, workspace_id, tournament_id, provider_entrant_id, provider_user_id,
                            prefix, gamertag, membership_state, membership_observed_at,
                            roster_snapshot_id, state, state_reason_code, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, ?, ?, ?, ?)""",
                        (enrollment_id, workspace_id, tournament_id, item["provider_entrant_id"],
                         item["provider_user_id"], item["prefix"], item["gamertag"], observed,
                         snapshot_id, state, reason, observed, observed),
                    )
                    added += 1
                    affected.append(enrollment_id)
                    continue
                enrollment_id = str(old["id"])
                old_tag = _text(old["gamertag"])
                tag_changed = old_tag != item["gamertag"]
                prefix_changed = _text(old["prefix"]) != item["prefix"]
                changed = tag_changed or prefix_changed
                collision = item["provider_entrant_id"] in collision_ids
                current_state = str(old["state"] or "awaiting_provider")
                if collision:
                    state, reason = "needs_review", "gamertag_collision"
                elif tag_changed:
                    state, reason = "needs_review", "provider_identity_changed"
                elif current_state in {"rejected", "needs_review"}:
                    # Preserve explicit organizer review/rejection until they
                    # choose a corrective action; synchronization must not
                    # silently approve it.
                    state, reason = current_state, old["state_reason_code"]
                else:
                    state, reason = current_state, old["state_reason_code"]
                await db.execute(
                    """UPDATE tournament_player_enrollments
                       SET provider_user_id=?, prefix=?, gamertag=?, membership_state='confirmed',
                           membership_observed_at=?, roster_snapshot_id=?, state=?, state_reason_code=?, updated_at=?
                       WHERE id=? AND workspace_id=? AND tournament_id=?""",
                    (item["provider_user_id"], item["prefix"], item["gamertag"], observed,
                     snapshot_id, state, reason, observed, enrollment_id, workspace_id, tournament_id),
                )
                if changed or collision:
                    updated += 1
                    affected.append(enrollment_id)
                else:
                    unchanged += 1

            for row in old_rows:
                entrant_id = str(row["provider_entrant_id"])
                if entrant_id in current_ids:
                    continue
                enrollment_id = str(row["id"])
                await db.execute(
                    """UPDATE tournament_player_enrollments
                       SET membership_state='missing', state='needs_review', state_reason_code='provider_entrant_removed',
                           membership_observed_at=?, updated_at=?
                       WHERE id=? AND workspace_id=? AND tournament_id=?""",
                    (observed, observed, enrollment_id, workspace_id, tournament_id),
                )
                removed += 1
                affected.append(enrollment_id)
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return RosterSyncResult(
        snapshot_id=snapshot_id, provider_type=provider_type,
        tournament_id=tournament_id, external_scope_id=external_scope_id,
        provider_revision=provider_revision, observed_at=observed,
        added=added, updated=updated, unchanged=unchanged, removed=removed,
        collision_count=len(collisions), affected_enrollment_ids=tuple(affected),
    )


async def synchronize_provider_roster(*args: Any, **kwargs: Any) -> RosterSyncResult:
    """Descriptive alias for callers outside the registration router."""

    return await sync_provider_roster(*args, **kwargs)


async def recheck_provider_roster(
    tournament_id: str,
    workspace_id: str,
    *,
    provider_type: str,
    provider_account_id: str,
    external_scope_id: str,
    provider_tournament_id: str,
    provider: Any,
) -> RosterSyncResult:
    """Fetch and synchronize the selected scope through an injected adapter."""

    if provider is None:
        raise RegistrationError("provider_adapter_required")
    tournament = await provider.fetch_tournament(provider_tournament_id)
    events = (tournament.get("events") if isinstance(tournament, Mapping) else getattr(tournament, "events", None)) if tournament is not None else None
    def event_id(event: Any) -> str:
        return str(event.get("id", "") if isinstance(event, Mapping) else getattr(event, "id", ""))
    selected = next((event for event in (events or []) if event_id(event) == str(external_scope_id)), None)
    if selected is None and provider_type == "challonge" and events:
        selected = events[0] if len(events) == 1 and event_id(events[0]) == str(external_scope_id) else None
    if selected is None:
        raise RegistrationError("provider_scope_not_found")
    raw_entrants = (selected.get("entrants") if isinstance(selected, Mapping) else getattr(selected, "entrants", [])) or []
    if isinstance(selected, Mapping):
        if provider_type == "startgg":
            from backend.core.providers.startgg.entrants import map_event_entrants
            raw_entrants = map_event_entrants(selected)
        elif provider_type == "challonge":
            from backend.core.providers.challonge.entrants import map_bracket_entrants
            raw_entrants = map_bracket_entrants(raw_entrants)
    return await sync_provider_roster(
        tournament_id, workspace_id, provider_type=provider_type,
        provider_account_id=provider_account_id, external_scope_id=external_scope_id,
        entrants=raw_entrants,
        provider_revision=(tournament.get("revision") if isinstance(tournament, Mapping) else getattr(tournament, "revision", None)),
    )


# Common API spelling used by explicit organizer Recheck actions.
explicit_recheck = recheck_provider_roster


__all__ = [
    "RosterSyncResult",
    "canonical_entrant",
    "explicit_recheck",
    "recheck_provider_roster",
    "roster_fingerprint",
    "sync_provider_roster",
    "synchronize_provider_roster",
]
