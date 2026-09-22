"""Local tournament materialization and activation transactions."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.core import database
from backend.core.storage import dbapi, is_postgres
from backend.core.tournament_readiness import compute_readiness
from backend.core.tournament_setup import DraftError, DraftRevisionConflict, get_draft
from backend.core.workflow_outbox import build_initial_sync_event
from backend.core.tournament_operating_profile import validate_operating_profile


class ActivationError(RuntimeError):
    pass


async def _ensure_discord_destination_id(
    db: Any,
    *,
    account_id: str,
    workspace_id: str,
    value: str,
    destination_type: str,
) -> str:
    """Return a same-workspace destination ID for an ID or external channel ID."""
    candidate = str(value or "").strip()
    if not candidate:
        raise ActivationError("Discord destination is required when Discord is enabled.")
    row = await (await db.execute(
        """SELECT id FROM integration_destinations
            WHERE account_id=? AND workspace_id=? AND status='active'
              AND (id=? OR external_id=?)
            ORDER BY CASE WHEN id=? THEN 0 ELSE 1 END, created_at
            LIMIT 1""",
        (account_id, workspace_id, candidate, candidate, candidate),
    )).fetchone()
    if row:
        return str(row[0])

    destination_id = str(uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"aitob:{workspace_id}:{account_id}:discord-destination:{candidate}",
    ))
    row = await (await db.execute(
        """INSERT INTO integration_destinations
               (id, account_id, workspace_id, destination_type, external_id, display_name)
            VALUES (?, ?, ?, ?, ?, 'Tournament destination')
            ON CONFLICT(account_id, destination_type, external_id) DO UPDATE SET
               status='active'
            RETURNING id""",
        (destination_id, account_id, workspace_id, destination_type, candidate),
    )).fetchone()
    return str(row[0])


async def _persist_materialized_settings(db: Any, draft: dict[str, Any], tournament_id: str, workspace_id: str, actor_id: str, now: str) -> None:
    """Project wizard answers into the durable tournament settings tables."""
    provider = draft.get("provider_scope") or {}
    selected = provider.get("selected_scope") or {}
    tournament_facts = provider.get("tournament") or {}
    review = draft.get("tournament_review") or {}
    start_wave = provider.get("start_in_wave") or {}
    wave_confirmation = start_wave.get("organizer_confirmation") or {}
    scope_kind = str(selected.get("kind") or "event").lower()
    if scope_kind not in {"event", "bracket"}:
        scope_kind = "event"
    await db.execute(
        """INSERT INTO provider_scope_bindings
           (tournament_id, workspace_id, provider_account_id, provider_type,
            external_tournament_id, external_scope_kind, external_scope_id,
            external_tournament_slug, external_scope_slug, provider_snapshot_json,
            observed_at, sync_state, start_in_wave_state, wave_monitoring_mode,
            wave_confirmed_by, wave_confirmed_at, wave_monitoring_state,
            wave_last_observed_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_started', ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(tournament_id) DO UPDATE SET
            provider_account_id=excluded.provider_account_id, provider_type=excluded.provider_type,
            external_tournament_id=excluded.external_tournament_id, external_scope_kind=excluded.external_scope_kind,
            external_scope_id=excluded.external_scope_id, external_tournament_slug=excluded.external_tournament_slug,
            external_scope_slug=excluded.external_scope_slug, provider_snapshot_json=excluded.provider_snapshot_json,
            observed_at=excluded.observed_at, start_in_wave_state=excluded.start_in_wave_state,
            wave_monitoring_mode=excluded.wave_monitoring_mode, wave_confirmed_by=excluded.wave_confirmed_by,
            wave_confirmed_at=excluded.wave_confirmed_at, wave_monitoring_state=excluded.wave_monitoring_state,
            wave_last_observed_at=excluded.wave_last_observed_at, updated_at=excluded.updated_at""",
        (tournament_id, workspace_id, str(provider.get("account_id") or provider.get("provider_account_id") or ""),
         str(provider.get("provider") or provider.get("provider_type") or "startgg"),
         str(tournament_facts.get("external_id") or ""), scope_kind, str(selected.get("external_id") or ""),
         tournament_facts.get("canonical_slug"), selected.get("canonical_slug"), json.dumps(provider, ensure_ascii=False),
         provider.get("observed_at") or now, str(start_wave.get("state") or "unknown"),
         str(start_wave.get("monitoring_mode") or "off"), actor_id if wave_confirmation.get("confirmed") else None,
         wave_confirmation.get("confirmed_at"), str(start_wave.get("monitoring_state") or "not_applicable"),
         start_wave.get("observed_at") or provider.get("observed_at"), now, now),
    )

    display_name = str(review.get("display_name") or _fact_value(tournament_facts.get("name")) or "Untitled tournament")
    await db.execute(
        """INSERT INTO tournament_brands (tournament_id, workspace_id, display_name, short_name, logo_asset_id, updated_by, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(tournament_id) DO UPDATE SET display_name=excluded.display_name,
            short_name=excluded.short_name, logo_asset_id=excluded.logo_asset_id,
            updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
        (tournament_id, workspace_id, display_name, review.get("short_name"), review.get("logo_asset_id"), actor_id, now),
    )

    profile = validate_operating_profile(draft.get("operating_profile") or {}).as_dict()
    await db.execute(
        """INSERT INTO tournament_operating_profiles
           (tournament_id, workspace_id, preset_key, preset_version, attendance_source,
            attendance_timeout_seconds, reminder_schedule_json, escalation_enabled,
            result_approval_policy, automatic_calls_enabled, max_concurrent_bot_matches,
            automatic_call_stop_threshold, stream_match_policy, created_at, updated_at, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(tournament_id) DO UPDATE SET preset_key=excluded.preset_key,
            preset_version=excluded.preset_version, attendance_source=excluded.attendance_source,
            attendance_timeout_seconds=excluded.attendance_timeout_seconds,
            reminder_schedule_json=excluded.reminder_schedule_json, escalation_enabled=excluded.escalation_enabled,
            result_approval_policy=excluded.result_approval_policy, automatic_calls_enabled=excluded.automatic_calls_enabled,
            max_concurrent_bot_matches=excluded.max_concurrent_bot_matches,
            automatic_call_stop_threshold=excluded.automatic_call_stop_threshold,
            stream_match_policy=excluded.stream_match_policy, updated_at=excluded.updated_at, updated_by=excluded.updated_by""",
        (tournament_id, workspace_id, profile["preset_key"], profile["preset_version"], profile["attendance_source"],
         profile["attendance_timeout_seconds"], json.dumps(profile["reminder_schedule"]), bool(profile["escalation_enabled"]),
         profile["result_approval_policy"], bool(profile["automatic_calls_enabled"]), profile["max_concurrent_bot_matches"],
         profile["automatic_call_stop_threshold"], profile["stream_match_policy"], now, now, actor_id),
    )

    discord = draft.get("discord_setup") or {}
    registration = discord.get("registration") or {}
    guild_id = str(discord.get("guild_id") or "")
    match_destination = str(discord.get("destination_external_id") or registration.get("destination_external_id") or "")
    if discord.get("enabled"):
        account_row = await (await db.execute(
            "SELECT id FROM integration_accounts WHERE workspace_id=? AND provider_type='discord' AND status='active' ORDER BY created_at LIMIT 1",
            (workspace_id,),
        )).fetchone()
        discord_account_id = str(discord.get("discord_account_id") or discord.get("account_id") or (account_row[0] if account_row else ""))
        if not discord_account_id:
            raise ActivationError("An active Discord integration account is required.")
        selected_account = await (await db.execute(
            """SELECT id FROM integration_accounts
                WHERE id=? AND workspace_id=? AND provider_type='discord' AND status='active'""",
            (discord_account_id, workspace_id),
        )).fetchone()
        if not selected_account:
            raise ActivationError("The selected Discord account is unavailable in this workspace.")
        match_destination_id = await _ensure_discord_destination_id(
            db,
            account_id=discord_account_id,
            workspace_id=workspace_id,
            value=match_destination,
            destination_type="match_call_channel",
        )
        escalation_destination_id = await _ensure_discord_destination_id(
            db,
            account_id=discord_account_id,
            workspace_id=workspace_id,
            value=str(discord.get("escalation_destination_id") or match_destination),
            destination_type="escalation_channel",
        )
        await db.execute("UPDATE tournaments SET discord_account_id=? WHERE slug=? AND workspace_id=?", (discord_account_id, tournament_id, workspace_id))
        await db.execute(
            """INSERT INTO tournament_discord_bindings
               (tournament_id, workspace_id, discord_account_id, guild_id, match_destination_id,
                escalation_destination_id, moderator_role_external_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tournament_id) DO UPDATE SET discord_account_id=excluded.discord_account_id,
                guild_id=excluded.guild_id, match_destination_id=excluded.match_destination_id,
                escalation_destination_id=excluded.escalation_destination_id,
                moderator_role_external_id=excluded.moderator_role_external_id,
                status=excluded.status, updated_at=excluded.updated_at""",
            (tournament_id, workspace_id, discord_account_id, guild_id, match_destination_id,
             escalation_destination_id,
             discord.get("moderator_role_external_id") or registration.get("verified_role_external_id"),
             "ready" if guild_id and match_destination and discord_account_id else "degraded", now, now),
        )

    registration_enabled = bool(registration.get("enabled") and registration.get("destination_external_id") and registration.get("opens_at") and registration.get("closes_at"))
    await db.execute(
        """INSERT INTO tournament_registration_configs
           (tournament_id, workspace_id, enabled, destination_external_id, opens_at, closes_at,
            display_timezone, require_provider_registration, gamertag_verification_policy,
            startgg_bio_verification_enabled, image_policy, verified_role_external_id,
            announcement_policy_json, status, created_at, updated_at, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(tournament_id) DO UPDATE SET enabled=excluded.enabled,
            destination_external_id=excluded.destination_external_id, opens_at=excluded.opens_at,
            closes_at=excluded.closes_at, display_timezone=excluded.display_timezone,
            require_provider_registration=excluded.require_provider_registration,
            gamertag_verification_policy=excluded.gamertag_verification_policy,
            startgg_bio_verification_enabled=excluded.startgg_bio_verification_enabled,
            image_policy=excluded.image_policy, verified_role_external_id=excluded.verified_role_external_id,
            announcement_policy_json=excluded.announcement_policy_json, status=excluded.status,
            updated_at=excluded.updated_at, updated_by=excluded.updated_by""",
        (tournament_id, workspace_id, registration_enabled, registration.get("destination_external_id"),
         registration.get("opens_at") or None, registration.get("closes_at") or None,
         registration.get("display_timezone") or "UTC", bool(registration.get("require_provider_registration", True)),
         registration.get("gamertag_verification_policy") or "match_or_set_nickname",
         bool(registration.get("startgg_bio_verification_enabled", False)), registration.get("image_policy") or "optional",
         registration.get("verified_role_external_id"), json.dumps(registration.get("announcement_policy") or {}),
         "scheduled" if registration_enabled else "disabled", now, now, actor_id),
    )


def _fact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("value")
    return value


async def materialize_draft(draft_id: str, workspace_id: str, actor_id: str, *, expected_revision: int) -> dict[str, Any]:
    draft = await get_draft(draft_id, workspace_id)
    if int(draft["revision"]) != int(expected_revision):
        raise DraftRevisionConflict(draft)
    if draft["status"] == "materialized" and draft.get("materialized_tournament_id"):
        return {"tournament_id": draft["materialized_tournament_id"], "status": "materialized", "replayed": True}
    readiness = await compute_readiness(draft_id, workspace_id, purpose="materialize")
    if readiness["state"] == "blocked":
        raise ActivationError("readiness_blocked")
    provider = draft.get("provider_scope") or {}
    selected = provider.get("selected_scope") or {}
    tournament_facts = provider.get("tournament") or {}
    review = draft.get("tournament_review") or {}
    slug = str(review.get("slug") or tournament_facts.get("canonical_slug") or f"aitob-{draft_id[:12]}").strip().lower()
    # Local slugs are workspace scoped by the migration target; keep collisions
    # deterministic during the current compatibility period.
    tournament_id = slug
    now = datetime.now(UTC).isoformat()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            existing = await (await db.execute("SELECT slug, workspace_id FROM tournaments WHERE slug=?", (slug,))).fetchone()
            if existing and str(existing["workspace_id"] or "") != str(workspace_id):
                slug = f"{slug}-{draft_id[:8]}"
                tournament_id = slug
            await db.execute(
                """INSERT INTO tournaments (slug, name, event_name, event_id, game, raw_data, workspace_id, provider_type, provider_tournament_id, provider_account_id, provider_sync_status, auto_dq_enabled, provider_dq_timer_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', FALSE, ?)
                   ON CONFLICT(slug) DO UPDATE SET name=excluded.name,
                    provider_dq_timer_seconds=excluded.provider_dq_timer_seconds
                   WHERE tournaments.workspace_id=?""",
                (slug, str(review.get("display_name") or _fact_value(tournament_facts.get("name")) or "Untitled tournament"), _fact_value(selected.get("name")), selected.get("external_id"), _fact_value(selected.get("game")), json.dumps({"draft_id": draft_id, "provider": provider}, ensure_ascii=False), workspace_id, provider.get("provider") or provider.get("provider_type") or "startgg", tournament_facts.get("external_id"), provider.get("account_id") or provider.get("provider_account_id"), review.get("provider_dq_timer_seconds") if (provider.get("provider") or provider.get("provider_type") or "startgg") == "startgg" else None, workspace_id),
            )
            await _persist_materialized_settings(db, draft, tournament_id, workspace_id, actor_id, now)
            await db.execute("UPDATE tournament_setup_drafts SET status='materialized', materialized_tournament_id=?, revision=revision+1, updated_by=?, updated_at=? WHERE id=? AND workspace_id=? AND revision=?", (tournament_id, actor_id, now, draft_id, workspace_id, expected_revision))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return {"tournament_id": tournament_id, "status": "materialized", "replayed": False, "revision": int(expected_revision) + 1}


async def activate_tournament(workspace_id: str, tournament_id: str, actor_id: str, *, idempotency_key: str = "1") -> dict[str, Any]:
    event = build_initial_sync_event(workspace_id=workspace_id, tournament_id=tournament_id, activation_version=idempotency_key)
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        await db.execute("BEGIN")
        try:
            tournament = await (await db.execute("SELECT * FROM tournaments WHERE slug=? AND workspace_id=?", (tournament_id, workspace_id))).fetchone()
            if not tournament:
                raise ActivationError("tournament_not_found")
            await db.execute("UPDATE tournaments SET provider_sync_status='active' WHERE slug=? AND workspace_id=?", (tournament_id, workspace_id))
            await db.execute(
                """INSERT INTO workflow_outbox (event_id, match_id, event_type, payload_json, deduplication_key, status, attempts, next_attempt_at, workspace_id)
                   VALUES (?, ?, ?, ?, ?, 'pending', 0, NULL, ?) ON CONFLICT(deduplication_key) DO NOTHING""",
                (event["event_id"], event["match_id"], event["event_type"], json.dumps(event["payload"], ensure_ascii=False), event["deduplication_key"], workspace_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return {"tournament_id": tournament_id, "status": "active", "initial_sync_queued": True, "idempotency_key": event["deduplication_key"]}


__all__ = ["ActivationError", "materialize_draft", "activate_tournament"]
