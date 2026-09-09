"""Workspace plan and usage-limit policy.

Entitlements are deliberately local and non-commercial for now.  A missing
row means the workspace is on the free/non-billed plan; it does not grant an
unbounded bypass.  This module contains policy only: callers still perform the
actual mutation through their normal repository/service transaction.
"""
from __future__ import annotations

import json
from typing import Any

from backend.core import database
from backend.core.storage import dbapi as aiosqlite


# Conservative development defaults.  ``None`` is intentionally not used for
# free-plan resource limits: a free workspace must have an enforceable floor.
DEFAULT_FREE_LIMITS: dict[str, int] = {
    "tournaments": 25,
    "stations": 32,
    "members": 100,
    "integrations": 25,
    "provider_requests_per_month": 500,
    "ai_requests_per_hour": 30,
    "ai_tokens_per_hour": 60_000,
}

RESOURCE_TABLES: dict[str, tuple[str, str]] = {
    "tournaments": ("tournaments", "workspace_id"),
    "stations": ("stations", "workspace_id"),
    "members": ("workspace_memberships", "workspace_id"),
    "integrations": ("integration_accounts", "workspace_id"),
}


class EntitlementLimitExceeded(PermissionError):
    """A workspace reached a configured plan limit."""

    def __init__(self, resource: str, limit: int, current: int, requested: int = 1):
        self.resource, self.limit, self.current, self.requested = resource, limit, current, requested
        super().__init__(f"Workspace {resource} limit reached ({current}/{limit}).")


def _limits_from_json(value: Any) -> dict[str, int]:
    if value in (None, "", "{}"):
        return {}
    try:
        raw = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Stored workspace entitlement limits are invalid") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Stored workspace entitlement limits are invalid")
    parsed: dict[str, int] = {}
    for key, item in raw.items():
        if key not in DEFAULT_FREE_LIMITS:
            # Unknown future limits must not be silently interpreted as a
            # current resource or make an existing limit less restrictive.
            continue
        try:
            number = int(item)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Stored workspace entitlement limits are invalid") from exc
        if number < 0:
            raise RuntimeError("Stored workspace entitlement limits are invalid")
        parsed[key] = number
    return parsed


async def get_workspace_entitlement(workspace_id: str) -> dict[str, Any]:
    """Return a safe effective entitlement projection for one workspace."""
    if not workspace_id:
        raise ValueError("workspace_id is required")
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT workspace_id, plan_key, billing_state, limits_json, usage_json, updated_at "
            "FROM workspace_entitlements WHERE workspace_id=?", (workspace_id,)
        )).fetchone()
    if not row:
        return {
            "workspace_id": workspace_id,
            "plan_key": "free",
            "billing_state": "non_billed",
            "limits": dict(DEFAULT_FREE_LIMITS),
            "usage": {},
            "updated_at": None,
        }
    limits = dict(DEFAULT_FREE_LIMITS)
    limits.update(_limits_from_json(row["limits_json"]))
    try:
        usage = json.loads(row["usage_json"] or "{}")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Stored workspace entitlement usage is invalid") from exc
    if not isinstance(usage, dict):
        raise RuntimeError("Stored workspace entitlement usage is invalid")
    return {
        "workspace_id": str(row["workspace_id"]),
        "plan_key": str(row["plan_key"] or "free"),
        "billing_state": str(row["billing_state"] or "non_billed"),
        "limits": limits,
        "usage": usage,
        "updated_at": row["updated_at"],
    }


async def get_workspace_limit(workspace_id: str | None, key: str, fallback: int | None = None) -> int | None:
    """Return an effective limit without leaking entitlement internals."""
    if workspace_id is None:
        return fallback
    entitlement = await get_workspace_entitlement(workspace_id)
    return entitlement["limits"].get(key, fallback)


async def workspace_resource_count(workspace_id: str, resource: str) -> int:
    """Count active workspace-owned resources for capacity checks."""
    try:
        table, column = RESOURCE_TABLES[resource]
    except KeyError as exc:
        raise ValueError(f"Unknown entitlement resource: {resource}") from exc
    # Table/column names come only from the static mapping above.
    async with aiosqlite.connect(database.DB_PATH) as db:
        row = await (await db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column}=?"
            + (" AND status='active'" if resource == "members" else ""),
            (workspace_id,),
        )).fetchone()
    return int(row[0])


async def require_workspace_capacity(
    workspace_id: str | None,
    resource: str,
    *,
    additional: int = 1,
    current: int | None = None,
) -> None:
    """Fail closed when a workspace would exceed its effective limit.

    The check is intentionally performed before provider calls and before the
    caller's mutation.  A caller that needs strict concurrent reservation must
    perform this policy check inside its existing repository transaction; this
    helper never opens a competing transaction or creates usage rows.
    """
    if workspace_id is None:
        return  # Explicitly retain unscoped legacy/test callers.
    if additional < 1:
        raise ValueError("additional must be positive")
    limit = await get_workspace_limit(workspace_id, resource)
    if limit is None:
        return
    observed = await workspace_resource_count(workspace_id, resource) if current is None else int(current)
    if observed + additional > int(limit):
        raise EntitlementLimitExceeded(resource, int(limit), observed, additional)


async def set_workspace_entitlement(
    workspace_id: str, *, plan_key: str = "free", billing_state: str = "non_billed",
    limits: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Persist a validated local entitlement (billing remains out of scope)."""
    if plan_key not in {"free", "managed"}:
        raise ValueError("Unsupported plan")
    if billing_state not in {"non_billed", "active", "past_due", "expired"}:
        raise ValueError("Unsupported billing state")
    try:
        clean = _limits_from_json(limits or {})
    except RuntimeError as exc:
        raise ValueError("Entitlement limits are invalid") from exc
    payload = json.dumps(clean, separators=(",", ":"))
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute(
            "INSERT INTO workspace_entitlements (workspace_id, plan_key, billing_state, limits_json, updated_at) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(workspace_id) DO UPDATE SET plan_key=excluded.plan_key, "
            "billing_state=excluded.billing_state, limits_json=excluded.limits_json, updated_at=CURRENT_TIMESTAMP",
            (workspace_id, plan_key, billing_state, payload),
        )
        await db.commit()
    return await get_workspace_entitlement(workspace_id)
