"""Compatibility boundary for the canonical Prefix/Gamertag vocabulary."""
from __future__ import annotations

from typing import Any, Mapping


def canonical_player_projection(row: Mapping[str, Any] | None) -> dict[str, Any]:
    value = dict(row or {})
    prefix = value.get("prefix") if value.get("prefix") is not None else value.get("team")
    gamertag = value.get("gamertag") if value.get("gamertag") is not None else value.get("gamer_tag")
    result = {"id": value.get("id") or value.get("discord_id"), "discord_id": value.get("discord_id"), "prefix": prefix, "gamertag": gamertag, "country": value.get("country"), "cfn_id": value.get("cfn_id"), "avatar_path": value.get("avatar_path"), "workspace_id": value.get("workspace_id")}
    return result


def legacy_player_projection(row: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project canonical data for legacy consumers only."""
    canonical = canonical_player_projection(row)
    return {**canonical, "team": canonical.get("prefix"), "gamer_tag": canonical.get("gamertag")}


__all__ = ["canonical_player_projection", "legacy_player_projection"]
