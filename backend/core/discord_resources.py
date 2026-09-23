"""Safe Discord resource discovery projections and permission evaluation."""
from __future__ import annotations

from typing import Any, Mapping

PERMISSION_BITS = {
    "view_channel": 10,
    "send_messages": 11,
    "embed_links": 14,
    "read_message_history": 16,
    "manage_nicknames": 27,
    "manage_roles": 28,
    "manage_threads": 34,
    "create_public_threads": 35,
    "send_messages_in_threads": 38,
}
REQUIRED_PERMISSIONS = tuple(PERMISSION_BITS)


def permissions_from_bitfield(value: int | str | None) -> dict[str, bool]:
    bits = int(value or 0)
    if bits & (1 << 3):
        return {name: True for name in REQUIRED_PERMISSIONS}
    return {name: bool(bits & (1 << bit)) for name, bit in PERMISSION_BITS.items()}


def effective_permissions(base: Mapping[str, bool] | None, *, role_overwrites: Mapping[str, bool] | None = None, member_overwrites: Mapping[str, bool] | None = None) -> dict[str, bool]:
    result = {name: bool((base or {}).get(name, False)) for name in REQUIRED_PERMISSIONS}
    for source in (role_overwrites or {}, member_overwrites or {}):
        for key, value in source.items():
            if key in result:
                result[key] = bool(value)
    return result


def permission_checks(base: Mapping[str, bool] | None, *, role_overwrites: Mapping[str, bool] | None = None, member_overwrites: Mapping[str, bool] | None = None) -> list[dict[str, Any]]:
    perms = effective_permissions(base, role_overwrites=role_overwrites, member_overwrites=member_overwrites)
    return [{"permission": key, "allowed": value, "state": "ready" if value else "blocked", "reason_code": None if value else "missing_permission"} for key, value in perms.items()]


def project_resources(*, guilds: list[Mapping[str, Any]] | None = None, channels: list[Mapping[str, Any]] | None = None, roles: list[Mapping[str, Any]] | None = None, permissions: Mapping[str, bool] | None = None) -> dict[str, Any]:
    def safe(items: list[Mapping[str, Any]] | None, allowed: tuple[str, ...]) -> list[dict[str, Any]]:
        result = []
        for item in items or []:
            if item.get("id") is None:
                continue
            result.append({key: str(item[key]) for key in allowed if item.get(key) is not None})
        return result
    return {"guilds": safe(guilds, ("id", "name")), "channels": safe(channels, ("id", "name", "type", "parent_id")), "roles": safe(roles, ("id", "name")), "permissions": permission_checks(permissions)}


__all__ = ["effective_permissions", "permission_checks", "permissions_from_bitfield", "project_resources", "REQUIRED_PERMISSIONS"]
