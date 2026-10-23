"""Tournament Match Format & Set Rules (FT2 / FT3 / FT5).

Translates tournament operational policies and round names into canonical
best_of integers (and vice versa) for bracket sets, station agents, and overlays.
"""
from __future__ import annotations

import math
import re
from typing import Optional

# Standard fighting game set formats mapping to best_of (odd integer count)
# FT2 (First to 2) -> Best of 3
# FT3 (First to 3) -> Best of 5
# FT5 (First to 5) -> Best of 9
# FT7 (First to 7) -> Best of 13
FORMAT_TO_BEST_OF = {
    "ft2": 3,
    "ft3": 5,
    "ft4": 7,
    "ft5": 9,
    "ft7": 13,
}

BEST_OF_TO_FORMAT = {
    3: "ft2",
    5: "ft3",
    7: "ft4",
    9: "ft5",
    13: "ft7",
}

FINALS_PATTERNS = [
    re.compile(r"\bgrand\s+finals?\b", re.IGNORECASE),
    re.compile(r"\bwinners?\s+finals?\b", re.IGNORECASE),
    re.compile(r"\blosers?\s+finals?\b", re.IGNORECASE),
]

TOP8_PATTERNS = [
    *FINALS_PATTERNS,
    re.compile(r"\bsemi[-\s]?finals?\b", re.IGNORECASE),
    re.compile(r"\bsemis\b", re.IGNORECASE),
    re.compile(r"\bquarter[-\s]?finals?\b", re.IGNORECASE),
    re.compile(r"\bquarters\b", re.IGNORECASE),
    re.compile(r"\btop\s*8\b", re.IGNORECASE),
    re.compile(r"\btop\s*6\b", re.IGNORECASE),
]


def format_to_best_of(fmt: str | int | None, default: int = 3) -> int:
    """Normalize a format key ('ft2', 'ft3', 3, 5) into a canonical best_of integer."""
    if fmt is None:
        return default
    if isinstance(fmt, int):
        return fmt if fmt > 0 else default
    s = str(fmt).strip().lower()
    if s in FORMAT_TO_BEST_OF:
        return FORMAT_TO_BEST_OF[s]
    if s.isdigit():
        val = int(s)
        return val if val > 0 else default
    return default


def best_of_to_format(best_of: int | None, default: str = "ft2") -> str:
    """Return 'ft2', 'ft3', 'ft5', etc. from a best_of integer."""
    if best_of is None or best_of <= 0:
        return default
    if best_of in BEST_OF_TO_FORMAT:
        return BEST_OF_TO_FORMAT[best_of]
    ft = math.ceil(best_of / 2)
    return f"ft{ft}"


def resolve_match_best_of(
    round_name: Optional[str],
    default_format: str = "ft2",
    upgrade_rule: str = "finals_only",
    upgraded_format: str = "ft3",
) -> int:
    """Compute the appropriate best_of integer for a match set given its round name

    and tournament policies.
    """
    def_best_of = format_to_best_of(default_format, default=3)
    upg_best_of = format_to_best_of(upgraded_format, default=5)

    rule = str(upgrade_rule or "finals_only").strip().lower()
    if rule == "disabled":
        return def_best_of

    clean_round = str(round_name or "").strip()
    if not clean_round:
        return def_best_of

    if rule == "finals_only":
        for pat in FINALS_PATTERNS:
            if pat.search(clean_round):
                return upg_best_of
        return def_best_of

    if rule == "top8_finals":
        for pat in TOP8_PATTERNS:
            if pat.search(clean_round):
                return upg_best_of
        return def_best_of

    return def_best_of
