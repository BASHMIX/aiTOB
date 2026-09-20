"""Safe Manual/Assisted operating presets.

The profile only controls calling/reminders/escalation.  Automatic
disqualification is intentionally absent and cannot be enabled through this
module.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping, Literal

PresetKey = Literal["manual", "assisted"]


@dataclass(frozen=True, slots=True)
class OperatingProfile:
    preset_key: PresetKey = "manual"
    preset_version: int = 1
    attendance_source: str = "manual"
    attendance_timeout_seconds: int | None = 600
    reminder_schedule: tuple[int, ...] = (300, 120)
    escalation_enabled: bool = True
    result_approval_policy: str = "human_required"
    automatic_calls_enabled: bool = False
    max_concurrent_bot_matches: int = 0
    automatic_call_stop_threshold: int = 0
    stream_match_policy: str = "manual"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reminder_schedule"] = list(self.reminder_schedule)
        # Never expose a legacy automatic-DQ knob in a setup projection.
        data.pop("auto_dq_enabled", None)
        return data


def expand_preset(preset: PresetKey = "manual", *, version: int = 1) -> OperatingProfile:
    if preset == "manual":
        return OperatingProfile(preset_key="manual", preset_version=version)
    if preset == "assisted":
        return OperatingProfile(
            preset_key="assisted", preset_version=version, attendance_source="discord",
            attendance_timeout_seconds=600, reminder_schedule=(300, 120),
            escalation_enabled=True, automatic_calls_enabled=True,
            max_concurrent_bot_matches=2, automatic_call_stop_threshold=3,
            stream_match_policy="prefer_stream",
        )
    raise ValueError("Unsupported operating preset")


def validate_operating_profile(value: Mapping[str, Any] | None) -> OperatingProfile:
    raw = dict(value or {})
    preset = str(raw.get("preset_key") or raw.get("preset") or "manual").lower()
    profile = expand_preset(preset if preset in {"manual", "assisted"} else "manual")
    updates: dict[str, Any] = {}
    for key in ("attendance_source", "result_approval_policy", "stream_match_policy"):
        if key in raw and raw[key] is not None:
            updates[key] = str(raw[key]).strip()
    for key in ("attendance_timeout_seconds", "max_concurrent_bot_matches", "automatic_call_stop_threshold"):
        if key in raw and raw[key] is not None:
            parsed = int(raw[key])
            if parsed < 0:
                raise ValueError(f"{key} must be non-negative")
            updates[key] = parsed
    for key in ("escalation_enabled", "automatic_calls_enabled"):
        if key in raw:
            updates[key] = bool(raw[key])
    if "reminder_schedule" in raw:
        schedule = tuple(sorted({int(item) for item in (raw["reminder_schedule"] or []) if int(item) >= 0}, reverse=True))
        updates["reminder_schedule"] = schedule
    # No caller can turn on automatic calls under the Manual preset.
    if profile.preset_key == "manual":
        updates["automatic_calls_enabled"] = False
        updates["max_concurrent_bot_matches"] = 0
    return OperatingProfile(**{**asdict(profile), **updates})


def unfinished_match_stop_reached(unfinished_matches: int, profile: OperatingProfile) -> bool:
    threshold = int(profile.automatic_call_stop_threshold or 0)
    return threshold > 0 and int(unfinished_matches) >= threshold


__all__ = ["OperatingProfile", "expand_preset", "validate_operating_profile", "unfinished_match_stop_reached"]
