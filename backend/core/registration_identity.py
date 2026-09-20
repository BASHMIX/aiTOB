"""Deterministic identity checks used by tournament registration.

Identity resolution is deliberately exact.  This module normalizes Unicode
and whitespace only, compares the provider's competitive Gamertag with the
Discord username/display name/server nickname, and reports collisions for
organizer review.  It never chooses a fuzzy or first-match candidate.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import unicodedata
from typing import Any, Iterable, Mapping


GAMERTAG_METHODS = frozenset({
    "exact_discord_name",
    "set_server_nickname",
    "match_or_set_nickname",
})
BIO_METHOD = "startgg_bio"


def normalize_gamertag(value: Any) -> str:
    """Return the documented exact-comparison form of a Gamertag.

    NFKC handles visually equivalent Unicode forms; casefold handles Unicode
    case semantics; repeated whitespace is collapsed.  Punctuation and other
    characters remain significant, so this is not fuzzy matching.
    """

    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = " ".join(text.replace("\u200b", "").split())
    return text.casefold()


def discord_name_candidates(member: Mapping[str, Any] | Any) -> tuple[str, ...]:
    """Return normalized Discord identity labels in deterministic priority order."""

    if isinstance(member, Mapping):
        values = (
            member.get("username"),
            member.get("global_name"),
            member.get("display_name"),
            member.get("nickname"),
            member.get("server_nickname"),
        )
    else:
        values = (
            getattr(member, "name", None),
            getattr(member, "global_name", None),
            getattr(member, "display_name", None),
            getattr(member, "nick", None),
        )
    result: list[str] = []
    for value in values:
        normalized = normalize_gamertag(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def exact_gamertag_match(gamertag: Any, member_or_names: Mapping[str, Any] | Any) -> bool:
    """Compare a Gamertag to an exact Discord username/display label."""

    expected = normalize_gamertag(gamertag)
    return bool(expected) and expected in discord_name_candidates(member_or_names)


# Compatibility aliases make the policy easy to discover at call sites.
gamertag_matches_discord_name = exact_gamertag_match
compare_gamertag = exact_gamertag_match


@dataclass(frozen=True)
class GamertagCollision:
    normalized_gamertag: str
    entrant_ids: tuple[str, ...]
    gamertag_values: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_gamertag": self.normalized_gamertag,
            "entrant_ids": list(self.entrant_ids),
            "gamertag_values": list(self.gamertag_values),
        }


def _entrant_value(entrant: Mapping[str, Any] | Any, key: str, default: Any = None) -> Any:
    if isinstance(entrant, Mapping):
        return entrant.get(key, default)
    return getattr(entrant, key, default)


def detect_gamertag_collisions(entrants: Iterable[Mapping[str, Any] | Any]) -> tuple[GamertagCollision, ...]:
    """Find exact/normalized collisions without selecting a winner."""

    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for entrant in entrants:
        entrant_id = _entrant_value(entrant, "provider_entrant_id") or _entrant_value(entrant, "entrant_id") or _entrant_value(entrant, "id")
        gamertag = _entrant_value(entrant, "gamertag")
        normalized = normalize_gamertag(gamertag)
        if normalized and entrant_id is not None:
            groups[normalized].append((str(entrant_id), str(gamertag).strip()))
    collisions: list[GamertagCollision] = []
    for normalized, values in sorted(groups.items()):
        ids = tuple(sorted({item[0] for item in values}))
        if len(ids) > 1:
            tags = tuple(dict.fromkeys(item[1] for item in values))
            collisions.append(GamertagCollision(normalized, ids, tags))
    return tuple(collisions)


find_gamertag_collisions = detect_gamertag_collisions


def provider_verification_methods(provider_type: str, *, startgg_bio_enabled: bool = False) -> tuple[str, ...]:
    """Return methods visible for one provider and configuration."""

    provider = str(provider_type or "").strip().lower()
    methods = ["exact_discord_name", "set_server_nickname", "match_or_set_nickname"]
    if provider == "startgg" and startgg_bio_enabled:
        methods.append(BIO_METHOD)
    return tuple(methods)


available_verification_methods = provider_verification_methods


@dataclass(frozen=True)
class IdentityCheck:
    state: str
    method: str
    reason_code: str | None = None
    normalized_gamertag: str = ""
    matched_name: str | None = None
    allowed_actions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def matched(self) -> bool:
        return self.state == "matched"

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "method": self.method,
            "reason_code": self.reason_code,
            "normalized_gamertag": self.normalized_gamertag,
            "matched_name": self.matched_name,
            "allowed_actions": list(self.allowed_actions),
        }


def evaluate_identity(
    gamertag: Any,
    member: Mapping[str, Any] | Any,
    policy: str,
    *,
    collision: bool = False,
) -> IdentityCheck:
    """Evaluate one member under the organizer's exact policy.

    Nickname changes are represented as an allowed action for the Discord
    service; this pure function never performs a Discord mutation.
    """

    normalized = normalize_gamertag(gamertag)
    if policy not in GAMERTAG_METHODS:
        return IdentityCheck("needs_review", policy, "invalid_verification_policy", normalized)
    if collision:
        return IdentityCheck("needs_review", policy, "gamertag_collision", normalized, allowed_actions=("organizer_review",))
    names = discord_name_candidates(member)
    if normalized and normalized in names:
        matched = next((name for name in names if name == normalized), normalized)
        return IdentityCheck("matched", "exact_discord_name", None, normalized, matched)
    if policy in {"set_server_nickname", "match_or_set_nickname"}:
        return IdentityCheck(
            "nickname_required", "set_server_nickname", "discord_name_mismatch", normalized,
            allowed_actions=("set_server_nickname",),
        )
    return IdentityCheck("needs_review", "exact_discord_name", "discord_name_mismatch", normalized, allowed_actions=("organizer_review",))


__all__ = [
    "BIO_METHOD",
    "GAMERTAG_METHODS",
    "GamertagCollision",
    "IdentityCheck",
    "available_verification_methods",
    "compare_gamertag",
    "detect_gamertag_collisions",
    "discord_name_candidates",
    "evaluate_identity",
    "exact_gamertag_match",
    "find_gamertag_collisions",
    "gamertag_matches_discord_name",
    "normalize_gamertag",
    "provider_verification_methods",
]
