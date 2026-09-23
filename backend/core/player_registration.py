"""Workspace/tournament-scoped registration repositories.

This module owns persistence only.  Provider reads, Discord member resolution,
and image decoding are injected by later feature services so no external call
can run inside a database transaction here.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.core import database
from backend.core.storage import dbapi, is_postgres


class RegistrationError(ValueError):
    pass


ENROLLMENT_STATES = {
    "awaiting_provider", "awaiting_discord_link", "awaiting_identity",
    "awaiting_image", "awaiting_review", "ready", "rejected", "needs_review",
}
LINK_STATES = {"unlinked", "resolving", "linked", "not_in_guild", "invalid", "conflict"}
_SNOWFLAKE_RE = __import__("re").compile(r"^[0-9]{17,20}$")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return fallback


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_instant(value: Any) -> dt.datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        parsed = value
        # PostgreSQL TIMESTAMP columns return a naive datetime. Values entering
        # these repositories are validated as explicit UTC instants, so restore
        # that storage convention when reading them back.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        try:
            parsed = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise RegistrationError("registration_invalid_timestamp") from exc
    # A timestamp without an offset is ambiguous between organizer and server
    # clocks. Require an explicit instant; display_timezone is for rendering.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RegistrationError("registration_timestamp_must_include_timezone")
    return parsed.astimezone(dt.timezone.utc)


def _config(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    value = dict(row)
    value["enabled"] = bool(value.get("enabled"))
    value["require_provider_registration"] = bool(value.get("require_provider_registration"))
    value["startgg_bio_verification_enabled"] = bool(value.get("startgg_bio_verification_enabled"))
    value["announcement_policy"] = _loads(value.pop("announcement_policy_json", "{}"), {})
    value["schedule_version"] = int(value.get("schedule_version") or 1)
    return value


def _enrollment(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    value = dict(row)
    value["verification_methods"] = _loads(value.pop("verification_methods", "[]"), [])
    value["ready"] = value.get("state") == "ready"
    return value


async def _ensure_archive_profile(db: Any, enrollment: Mapping[str, Any], workspace_id: str, discord_user_id: str) -> str:
    """Return the single reusable Player Archive profile for a Discord member.

    This is called inside the enrollment transaction.  Registration facts are
    allowed to fill an empty profile, but never overwrite organizer edits on an
    existing profile.
    """
    profile_id = str(uuid.uuid4())
    display_name = str(enrollment.get("gamertag") or discord_user_id).strip() or discord_user_id
    prefix = str(enrollment.get("prefix") or "").strip() or None
    row = await (await db.execute(
        """INSERT INTO player_profiles
           (id, workspace_id, display_name, prefix, discord_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
           ON CONFLICT (workspace_id, discord_id) WHERE discord_id IS NOT NULL
           DO UPDATE SET updated_at = player_profiles.updated_at
           RETURNING id""",
        (profile_id, workspace_id, display_name, prefix, discord_user_id),
    )).fetchone()
    return str(row[0])


async def get_registration_config(tournament_id: str, workspace_id: str) -> dict[str, Any] | None:
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        row = await (await db.execute(
            "SELECT * FROM tournament_registration_configs WHERE tournament_id=? AND workspace_id=?",
            (tournament_id, workspace_id),
        )).fetchone()
    return _config(row)


async def upsert_registration_config(
    tournament_id: str,
    workspace_id: str,
    actor_id: str,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    enabled = bool(values.get("enabled", False))
    opens_at = values.get("opens_at")
    closes_at = values.get("closes_at")
    opens_instant = _parse_instant(opens_at)
    closes_instant = _parse_instant(closes_at)
    if enabled and (not values.get("destination_external_id") or not opens_at or not closes_at):
        raise RegistrationError("registration_destination_and_window_required")
    if opens_instant and closes_instant and opens_instant >= closes_instant:
        raise RegistrationError("registration_open_must_precede_close")
    display_timezone = str(values.get("display_timezone", "UTC")).strip()
    if not display_timezone:
        raise RegistrationError("registration_timezone_required")
    try:
        ZoneInfo(display_timezone)
    except ZoneInfoNotFoundError as exc:
        raise RegistrationError("registration_invalid_timezone") from exc
    policy = str(values.get("gamertag_verification_policy", "match_or_set_nickname"))
    if policy not in {"exact_discord_name", "set_server_nickname", "match_or_set_nickname"}:
        raise RegistrationError("invalid_gamertag_verification_policy")
    image_policy = str(values.get("image_policy", "optional"))
    if image_policy not in {"disabled", "optional", "required"}:
        raise RegistrationError("invalid_image_policy")
    now = _now()
    status = "disabled" if not enabled else "scheduled"
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            await db.execute(
                """INSERT INTO tournament_registration_configs
                   (tournament_id, workspace_id, enabled, destination_external_id, opens_at, closes_at,
                    display_timezone, require_provider_registration, gamertag_verification_policy,
                    startgg_bio_verification_enabled, image_policy, verified_role_external_id,
                    announcement_policy_json, status, created_at, updated_at, updated_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tournament_id) DO UPDATE SET
                    enabled=excluded.enabled, destination_external_id=excluded.destination_external_id,
                    opens_at=excluded.opens_at, closes_at=excluded.closes_at,
                    display_timezone=excluded.display_timezone,
                    require_provider_registration=excluded.require_provider_registration,
                    gamertag_verification_policy=excluded.gamertag_verification_policy,
                    startgg_bio_verification_enabled=excluded.startgg_bio_verification_enabled,
                    image_policy=excluded.image_policy, verified_role_external_id=excluded.verified_role_external_id,
                    announcement_policy_json=excluded.announcement_policy_json,
                    schedule_version=tournament_registration_configs.schedule_version + 1,
                    status=excluded.status,
                    updated_at=excluded.updated_at, updated_by=excluded.updated_by""",
                (tournament_id, workspace_id, enabled, values.get("destination_external_id"), opens_at, closes_at,
                 display_timezone, bool(values.get("require_provider_registration", True)),
                 policy, bool(values.get("startgg_bio_verification_enabled", False)), image_policy,
                 values.get("verified_role_external_id"), _dump(values.get("announcement_policy", {})), status,
                 now, now, actor_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        row = await (await db.execute(
            "SELECT * FROM tournament_registration_configs WHERE tournament_id=? AND workspace_id=?",
            (tournament_id, workspace_id),
        )).fetchone()
    return _config(row) or {}


def registration_window_state(config: Mapping[str, Any] | None, *, now: dt.datetime | None = None) -> str:
    """Compute the server-time registration state without trusting the UI."""

    if not config or not bool(config.get("enabled")):
        return "disabled"
    reference = now or dt.datetime.now(dt.timezone.utc)

    def parse(value: Any) -> dt.datetime | None:
        if not value:
            return None
        try:
            return _parse_instant(value)
        except RegistrationError:
            return None

    opens_at, closes_at = parse(config.get("opens_at")), parse(config.get("closes_at"))
    if not opens_at or not closes_at:
        return "degraded"
    if reference < opens_at:
        return "scheduled"
    if reference >= closes_at:
        return "closed"
    return "open"


async def set_registration_status(
    tournament_id: str,
    workspace_id: str,
    status: str,
    *,
    actor_id: str,
    reason: str | None = None,
    expected_schedule_version: int | None = None,
) -> dict[str, Any]:
    """Set an explicit organizer window status under a workspace lock."""

    if status not in {"scheduled", "open", "closed", "disabled", "degraded"}:
        raise RegistrationError("invalid_registration_status")
    now = _now()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            row = await (await db.execute(
                "SELECT * FROM tournament_registration_configs WHERE tournament_id=? AND workspace_id=?" + (" FOR UPDATE" if is_postgres() else ""),
                (tournament_id, workspace_id),
            )).fetchone()
            if not row:
                raise RegistrationError("registration_config_not_found")
            current_version = int(row["schedule_version"] or 1)
            if expected_schedule_version is not None and current_version != int(expected_schedule_version):
                raise RegistrationError("registration_schedule_version_conflict")
            # Replaying the same organizer action after a successful commit is
            # a no-op. This keeps its schedule version/outbox key stable and
            # lets the API safely retry after a lost response.
            if str(row["status"] or "") != status:
                await db.execute(
                    "UPDATE tournament_registration_configs SET status=?, schedule_version=?, updated_at=?, updated_by=? WHERE tournament_id=? AND workspace_id=?",
                    (status, current_version + 1, now, actor_id, tournament_id, workspace_id),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        row = await (await db.execute(
            "SELECT * FROM tournament_registration_configs WHERE tournament_id=? AND workspace_id=?",
            (tournament_id, workspace_id),
        )).fetchone()
    result = _config(row) or {}
    result["status_reason"] = reason
    return result


async def get_enrollment(enrollment_id: str, tournament_id: str, workspace_id: str) -> dict[str, Any] | None:
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        row = await (await db.execute(
            "SELECT * FROM tournament_player_enrollments WHERE id=? AND tournament_id=? AND workspace_id=?",
            (enrollment_id, tournament_id, workspace_id),
        )).fetchone()
    return _enrollment(row)


async def list_enrollments(
    tournament_id: str,
    workspace_id: str,
    *,
    state: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: list[Any] = [tournament_id, workspace_id]
    where = "tournament_id=? AND workspace_id=?"
    if state:
        if state not in ENROLLMENT_STATES:
            raise RegistrationError("invalid_enrollment_state")
        where += " AND state=?"
        params.append(state)
    params.append(max(1, min(int(limit), 500)))
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        rows = await (await db.execute(
            "SELECT * FROM tournament_player_enrollments WHERE " + where + " ORDER BY updated_at DESC LIMIT ?",
            params,
        )).fetchall()
    return [_enrollment(row) for row in rows]


async def upsert_enrollment(
    tournament_id: str,
    workspace_id: str,
    *,
    provider_entrant_id: str | None = None,
    provider_user_id: str | None = None,
    prefix: str | None = None,
    gamertag: str | None = None,
    provider_identity_link_id: int | None = None,
    membership_state: str = "unmatched",
    state: str = "awaiting_provider",
) -> dict[str, Any]:
    if state not in ENROLLMENT_STATES:
        raise RegistrationError("invalid_enrollment_state")
    now = _now()
    enrollment_id = str(uuid.uuid4())
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            existing = None
            if provider_entrant_id:
                existing = await (await db.execute(
                    "SELECT id FROM tournament_player_enrollments WHERE tournament_id=? AND workspace_id=? AND provider_entrant_id=?" + (" FOR UPDATE" if is_postgres() else ""),
                    (tournament_id, workspace_id, provider_entrant_id),
                )).fetchone()
            if existing:
                enrollment_id = str(existing[0])
                await db.execute(
                    """UPDATE tournament_player_enrollments SET provider_user_id=?, prefix=?, gamertag=?,
                       provider_identity_link_id=?, membership_state=?, state=?, updated_at=?
                       WHERE id=? AND tournament_id=? AND workspace_id=?""",
                    (provider_user_id, prefix, gamertag, provider_identity_link_id, membership_state, state,
                     now, enrollment_id, tournament_id, workspace_id),
                )
            else:
                await db.execute(
                    """INSERT INTO tournament_player_enrollments
                       (id, workspace_id, tournament_id, provider_identity_link_id, provider_entrant_id,
                        provider_user_id, prefix, gamertag, membership_state, state, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (enrollment_id, workspace_id, tournament_id, provider_identity_link_id, provider_entrant_id,
                     provider_user_id, prefix, gamertag, membership_state, state, now, now),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        row = await (await db.execute(
            "SELECT * FROM tournament_player_enrollments WHERE id=? AND tournament_id=? AND workspace_id=?",
            (enrollment_id, tournament_id, workspace_id),
        )).fetchone()
    return _enrollment(row) or {}


async def transition_enrollment(
    enrollment_id: str,
    tournament_id: str,
    workspace_id: str,
    state: str,
    *,
    reason_code: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    if state not in ENROLLMENT_STATES:
        raise RegistrationError("invalid_enrollment_state")
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            row = await (await db.execute(
                "SELECT id FROM tournament_player_enrollments WHERE id=? AND tournament_id=? AND workspace_id=?" + (" FOR UPDATE" if is_postgres() else ""),
                (enrollment_id, tournament_id, workspace_id),
            )).fetchone()
            if not row:
                raise RegistrationError("enrollment_not_found")
            await db.execute(
                "UPDATE tournament_player_enrollments SET state=?, state_reason_code=?, approved_by=COALESCE(?, approved_by), updated_at=? WHERE id=? AND tournament_id=? AND workspace_id=?",
                (state, reason_code, actor_id, _now(), enrollment_id, tournament_id, workspace_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        row = await (await db.execute(
            "SELECT * FROM tournament_player_enrollments WHERE id=? AND tournament_id=? AND workspace_id=?",
            (enrollment_id, tournament_id, workspace_id),
        )).fetchone()
    return _enrollment(row) or {}


async def link_discord_member(
    enrollment_id: str,
    tournament_id: str,
    workspace_id: str,
    discord_user_id: str,
    *,
    actor_id: str,
    guild_id: str | None = None,
    member_exists: bool = True,
    is_bot: bool = False,
) -> dict[str, Any]:
    """Create or replace a tournament-scoped manual Discord link.

    Discord lookups happen before this transaction.  The caller supplies the
    resulting membership facts, keeping network calls outside the DB lock.
    """
    value = str(discord_user_id or "").strip()
    if not _SNOWFLAKE_RE.fullmatch(value) or is_bot:
        raise RegistrationError("invalid_discord_user")
    if not member_exists:
        raise RegistrationError("discord_member_not_in_guild")
    now = _now()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            target = await (await db.execute(
                "SELECT * FROM tournament_player_enrollments WHERE id=? AND tournament_id=? AND workspace_id=?",
                (enrollment_id, tournament_id, workspace_id),
            )).fetchone()
            if not target:
                raise RegistrationError("enrollment_not_found")
            conflict = await (await db.execute(
                "SELECT id FROM tournament_player_enrollments WHERE tournament_id=? AND workspace_id=? AND discord_user_id=? AND id<>?",
                (tournament_id, workspace_id, value, enrollment_id),
            )).fetchone()
            if conflict:
                raise RegistrationError("discord_user_already_linked")
            methods = _loads(target["verification_methods"], [])
            if not isinstance(methods, list):
                methods = []
            if "manual_discord_id" not in methods:
                methods.append("manual_discord_id")
            profile_id = await _ensure_archive_profile(db, dict(target), workspace_id, value)
            await db.execute(
                """UPDATE tournament_player_enrollments
                   SET player_profile_id=?, discord_user_id=?, discord_link_state='linked', discord_member_observed_at=?,
                       discord_link_updated_by=?, discord_link_updated_at=?, membership_state='matched',
                       verification_methods=?, gamertag_match_state=COALESCE(gamertag_match_state, 'not_checked'),
                       state=CASE WHEN state IN ('awaiting_discord_link','awaiting_identity','needs_review') THEN 'awaiting_identity' ELSE state END,
                       updated_at=?
                   WHERE id=? AND tournament_id=? AND workspace_id=?""",
                (profile_id, value, now, actor_id, now, _dump(methods), now, enrollment_id, tournament_id, workspace_id),
            )
            entrant_id = str(target.get("provider_entrant_id") or "").strip()
            if entrant_id:
                await db.execute(
                    """INSERT INTO tournament_player_links
                       (tournament_slug, entrant_id, player_discord_id, player_profile_id, workspace_id)
                       VALUES (?, ?, NULL, ?, ?)
                       ON CONFLICT(workspace_id, tournament_slug, entrant_id)
                       DO UPDATE SET player_discord_id=NULL, player_profile_id=excluded.player_profile_id,
                                     created_at=CURRENT_TIMESTAMP""",
                    (tournament_id, entrant_id, profile_id, workspace_id),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        row = await (await db.execute(
            "SELECT * FROM tournament_player_enrollments WHERE id=? AND tournament_id=? AND workspace_id=?",
            (enrollment_id, tournament_id, workspace_id),
        )).fetchone()
    result = _enrollment(row) or {}
    result["discord_guild_id"] = guild_id
    result["allowed_actions"] = ["unlink_discord"]
    return result


async def unlink_discord_member(
    enrollment_id: str,
    tournament_id: str,
    workspace_id: str,
    *,
    actor_id: str,
) -> dict[str, Any]:
    now = _now()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            row = await (await db.execute(
                "SELECT * FROM tournament_player_enrollments WHERE id=? AND tournament_id=? AND workspace_id=?",
                (enrollment_id, tournament_id, workspace_id),
            )).fetchone()
            if not row:
                raise RegistrationError("enrollment_not_found")
            await db.execute(
                """UPDATE tournament_player_enrollments SET discord_user_id=NULL,
                   discord_link_state='unlinked', discord_link_updated_by=?, discord_link_updated_at=?,
                   membership_state='unmatched', gamertag_match_state='not_checked',
                   state=CASE WHEN state='ready' THEN 'awaiting_discord_link' ELSE state END,
                   updated_at=? WHERE id=? AND tournament_id=? AND workspace_id=?""",
                (actor_id, now, now, enrollment_id, tournament_id, workspace_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        row = await (await db.execute(
            "SELECT * FROM tournament_player_enrollments WHERE id=? AND tournament_id=? AND workspace_id=?",
            (enrollment_id, tournament_id, workspace_id),
        )).fetchone()
    result = _enrollment(row) or {}
    result["allowed_actions"] = ["link_discord"]
    return result
