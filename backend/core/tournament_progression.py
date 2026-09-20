"""Read-only, provider-neutral match display projection."""
from __future__ import annotations

import re
from typing import Any


def _unresolved(value: object) -> bool:
    return not str(value or "").strip() or str(value).strip().lower() in {"tbd", "unknown", "none"}


def _bracket_side(round_name: str) -> str:
    text = round_name.lower()
    if "loser" in text:
        return "losers"
    if "winner" in text:
        return "winners"
    if "final" in text:
        return "finals"
    if "swiss" in text:
        return "swiss"
    if "round robin" in text:
        return "round_robin"
    return "unknown"


def project_match(match: dict[str, Any]) -> dict[str, Any]:
    """Build display data only; it makes no state, provider, or side-effect call."""
    raw = match.get("provider_state_raw")
    normalized = match.get("provider_state_normalized")
    has_v2 = any(value is not None for value in (raw, normalized, match.get("hub_status"), match.get("sync_status")))
    p1, p2 = match.get("p1_name"), match.get("p2_name")
    is_bye = str(raw or "").lower() in {"bye", "invalid", "cancelled", "canceled"}
    two_sided = not _unresolved(p1) and not _unresolved(p2) and not is_bye
    reason = None
    if is_bye:
        reason = "Provider marks this match as a bye or invalid"
    elif not two_sided:
        reason = "Awaiting opponent"
    round_name = str(match.get("round_name") or "")
    phase_group = str(match.get("phase_group") or "")
    order_match = re.search(r"(-?\d+)(?!.*\d)", round_name)
    progression = {
        "stage": str(match.get("event_name") or "Bracket"),
        "stage_kind": "group" if phase_group else "single",
        "group": phase_group or None,
        "bracket_side": _bracket_side(round_name),
        "round": round_name or None,
        "round_order": int(order_match.group(1)) if order_match else None,
        "display_path": " / ".join(part for part in [str(match.get("event_name") or "Bracket"), phase_group or None, round_name or None] if part),
    }
    discord = {
        "call_sent": bool(match.get("call_message_id")),
        "call_message_id": match.get("call_message_id"), "thread_id": match.get("thread_id") or match.get("discord_thread_id"),
        "called_at": match.get("called_at"), "player1_ready_at": match.get("player1_ready_at"),
        "player2_ready_at": match.get("player2_ready_at"), "attendance_deadline": match.get("attendance_deadline"),
    }
    return {
        "v2_available": has_v2,
        "legacy_status": match.get("status"),
        "state_axes": {
            "provider": {"raw": raw, "normalized": normalized},
            "hub_status": match.get("hub_status"),
            "broadcast_state": match.get("broadcast_state") or "off_air",
            "sync_status": match.get("sync_status"),
        } if has_v2 else None,
        "provider_diagnostics": {"raw_state": raw, "revision": match.get("provider_revision"), "observed_at": match.get("provider_observed_at")} if has_v2 else None,
        "progression": progression,
        "discord": discord if has_v2 else None,
        "eligibility": {"two_sided": two_sided, "actionable": two_sided and not is_bye, "reason": reason},
    }
