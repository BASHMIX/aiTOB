"""Start.gg Start-in-wave capability and monitoring state projection."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, Mapping

WaveState = Literal["verified_enabled", "verified_disabled", "unsupported", "unknown"]
MonitoringMode = Literal["off", "provider_verified", "organizer_confirmed"]
MonitoringState = Literal["not_applicable", "awaiting_bracket_start", "monitoring", "blocked"]


def project_start_in_wave(
    state: str | None,
    *,
    observed_at: str | None = None,
    organizer_confirmed: bool = False,
    bracket_started: bool = False,
    fresh: bool = True,
) -> dict[str, Any]:
    normalized = str(state or "unknown").lower()
    if normalized not in {"verified_enabled", "verified_disabled", "unsupported", "unknown"}:
        normalized = "unknown"
    mode: MonitoringMode = "provider_verified" if normalized == "verified_enabled" else ("organizer_confirmed" if organizer_confirmed and normalized in {"unsupported", "unknown"} else "off")
    if mode == "off":
        monitor: MonitoringState = "not_applicable" if normalized in {"verified_disabled", "unsupported"} else "blocked"
    elif not fresh:
        monitor = "blocked"
    elif bracket_started:
        monitor = "monitoring"
    else:
        monitor = "awaiting_bracket_start"
    return {
        "state": normalized, "observed_at": observed_at or datetime.now(UTC).isoformat(),
        "monitoring_mode": mode, "monitoring_state": monitor,
        "organizer_confirmation": {"confirmed": bool(organizer_confirmed), "confirmed_at": None},
    }


def monitor_transition(previous: Mapping[str, Any] | None, *, bracket_started: bool, fresh: bool = True) -> dict[str, Any]:
    prior = dict(previous or {})
    return project_start_in_wave(
        str(prior.get("state") or "unknown"),
        observed_at=prior.get("observed_at"),
        organizer_confirmed=bool((prior.get("organizer_confirmation") or {}).get("confirmed")),
        bracket_started=bracket_started,
        fresh=fresh,
    )


def confirmation_patch(*, confirmed: bool, actor_id: str | None = None, at: str | None = None) -> dict[str, Any]:
    stamp = at or datetime.now(UTC).isoformat()
    return {"confirmed": bool(confirmed), "confirmed_by": actor_id if confirmed else None, "confirmed_at": stamp if confirmed else None}


__all__ = ["project_start_in_wave", "monitor_transition", "confirmation_patch"]
