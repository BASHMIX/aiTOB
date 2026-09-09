"""Workspace plan and usage-limit policy.

Entitlements are deliberately local and non-commercial for now.  A missing
row means the workspace is on the free/non-billed plan; it does not grant an
unbounded bypass.  This module contains policy only: callers still perform the
actual mutation through their normal repository/service transaction.
"""
from __future__ import annotations

import json
import datetime as dt
import uuid
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
            "SELECT workspace_id, plan_key, billing_state, limits_json, usage_json, "
            "expires_at, suspended_at, updated_at "
            "FROM workspace_entitlements WHERE workspace_id=?", (workspace_id,)
        )).fetchone()
    if not row:
        return {
            "workspace_id": workspace_id,
            "plan_key": "free",
            "billing_state": "non_billed",
            "status": "non_billed",
            "expires_at": None,
            "suspended_at": None,
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
    expires_at = row["expires_at"]
    suspended_at = row["suspended_at"]
    status = "suspended" if suspended_at else str(row["billing_state"] or "non_billed")
    if not suspended_at and expires_at:
        try:
            parsed_expiry = dt.datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if parsed_expiry.tzinfo is None:
                parsed_expiry = parsed_expiry.replace(tzinfo=dt.timezone.utc)
            if parsed_expiry <= dt.datetime.now(dt.timezone.utc):
                status = "expired"
        except ValueError:
            raise RuntimeError("Stored workspace entitlement expiry is invalid") from None
    return {
        "workspace_id": str(row["workspace_id"]),
        "plan_key": str(row["plan_key"] or "free"),
        "billing_state": str(row["billing_state"] or "non_billed"),
        "status": status,
        "expires_at": expires_at,
        "suspended_at": suspended_at,
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


def _parse_subscription_expiry(value: str | dt.datetime | None) -> str | None:
    if value is None:
        return None
    parsed = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("expires_at must include a timezone")
    parsed = parsed.astimezone(dt.timezone.utc)
    if parsed <= dt.datetime.now(dt.timezone.utc):
        raise ValueError("expires_at must be in the future")
    return parsed.isoformat()


async def apply_manual_subscription(
    workspace_id: str,
    *,
    actor_user_id: str,
    action: str,
    plan_key: str | None = None,
    expires_at: str | dt.datetime | None = None,
    extend_days: int | None = None,
) -> dict[str, Any]:
    """Apply a local, non-payment entitlement as a platform-admin action.

    This is intentionally not a checkout or webhook path.  The mutation and
    its redacted audit event commit together, and no provider or billing
    service is contacted.
    """
    if not await database.is_active_platform_admin(actor_user_id):
        raise PermissionError("Platform administrator permission required")
    if action not in {"activate", "extend", "suspend"}:
        raise ValueError("Unsupported subscription action")
    if plan_key is not None and plan_key not in {"free", "managed"}:
        raise ValueError("Unsupported plan")
    if extend_days is not None and not 1 <= int(extend_days) <= 3650:
        raise ValueError("extend_days must be between 1 and 3650")
    requested_expiry = _parse_subscription_expiry(expires_at) if expires_at is not None else None
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            workspace = await (await db.execute(
                "SELECT id, status FROM workspaces WHERE id=?", (workspace_id,)
            )).fetchone()
            if not workspace:
                raise ValueError("Workspace not found")
            current = await (await db.execute(
                "SELECT plan_key, billing_state, expires_at, suspended_at "
                "FROM workspace_entitlements WHERE workspace_id=?", (workspace_id,)
            )).fetchone()
            now = dt.datetime.now(dt.timezone.utc)
            selected_plan = plan_key or (str(current["plan_key"]) if current else "free")
            selected_expiry = requested_expiry
            billing_state = "active"
            suspended_at = None
            if action == "activate":
                if selected_plan == "free":
                    billing_state = "non_billed"
                if selected_expiry is None and selected_plan == "managed":
                    raise ValueError("expires_at is required for a managed activation")
            elif action == "extend":
                if extend_days is None:
                    raise ValueError("extend_days is required for an extension")
                prior = None if not current else current["expires_at"]
                base = now
                if prior:
                    parsed_prior = dt.datetime.fromisoformat(str(prior).replace("Z", "+00:00"))
                    base = max(base, parsed_prior.replace(tzinfo=parsed_prior.tzinfo or dt.timezone.utc))
                selected_expiry = (base + dt.timedelta(days=int(extend_days))).isoformat()
                if current and current["suspended_at"]:
                    selected_plan = str(current["plan_key"] or selected_plan)
                billing_state = "active" if selected_plan == "managed" else "non_billed"
            else:  # suspend
                if not current:
                    raise ValueError("Workspace has no entitlement to suspend")
                selected_plan = str(current["plan_key"] or selected_plan)
                selected_expiry = current["expires_at"]
                billing_state = "expired"
                suspended_at = now.isoformat()
            await db.execute(
                """INSERT INTO workspace_entitlements
                   (workspace_id, plan_key, billing_state, expires_at, suspended_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(workspace_id) DO UPDATE SET
                     plan_key=excluded.plan_key, billing_state=excluded.billing_state,
                     expires_at=excluded.expires_at, suspended_at=excluded.suspended_at,
                     updated_at=CURRENT_TIMESTAMP""",
                (workspace_id, selected_plan, billing_state, selected_expiry, suspended_at),
            )
            await db.execute(
                """INSERT INTO audit_events
                   (id, workspace_id, actor_id, action, target_type, target_id, outcome, detail_json)
                   VALUES (?, ?, ?, 'subscription.manual_update', 'workspace', ?, 'accepted', ?)""",
                (
                    str(uuid.uuid4()), workspace_id, actor_user_id, workspace_id,
                    json.dumps({"action": action, "plan_key": selected_plan, "has_expiry": bool(selected_expiry)}, separators=(",", ":")),
                ),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return await get_workspace_entitlement(workspace_id)
