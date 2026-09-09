"""T041 free-plan entitlement enforcement is local and workspace-scoped."""
from __future__ import annotations

import json

import pytest

from backend.core import database
from backend.core.entitlements import (
    DEFAULT_FREE_LIMITS,
    EntitlementLimitExceeded,
    get_workspace_entitlement,
    require_workspace_capacity,
    set_workspace_entitlement,
    workspace_resource_count,
)


@pytest.fixture
async def entitlement_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "entitlements.sqlite"))
    await database.init_db()
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", ("ws-a", "ws-a", "A"))
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", ("ws-b", "ws-b", "B"))
        await db.execute("INSERT INTO workspace_entitlements (workspace_id, limits_json) VALUES (?, ?)", ("ws-a", json.dumps({"tournaments": 1})))
        await db.execute("INSERT INTO tournaments (slug, name, workspace_id) VALUES (?, ?, ?)", ("a/one", "One", "ws-a"))
        await db.execute("INSERT INTO tournaments (slug, name, workspace_id) VALUES (?, ?, ?)", ("b/one", "One", "ws-b"))
        await db.commit()
    return "ws-a", "ws-b"


@pytest.mark.asyncio
async def test_free_entitlement_is_effective_and_workspace_scoped(entitlement_db):
    owner, other = entitlement_db
    entitlement = await get_workspace_entitlement(owner)
    assert entitlement["plan_key"] == "free"
    assert entitlement["billing_state"] == "non_billed"
    assert entitlement["limits"]["tournaments"] == 1
    assert await workspace_resource_count(owner, "tournaments") == 1

    with pytest.raises(EntitlementLimitExceeded):
        await require_workspace_capacity(owner, "tournaments")
    # A matching resource in another workspace does not consume the owner's
    # allowance or expose a cross-tenant count.
    await require_workspace_capacity(other, "tournaments")


@pytest.mark.asyncio
async def test_missing_entitlement_does_not_become_unlimited(entitlement_db):
    _, other = entitlement_db
    entitlement = await get_workspace_entitlement(other)
    assert entitlement["limits"] == DEFAULT_FREE_LIMITS
    await require_workspace_capacity(other, "tournaments")


@pytest.mark.asyncio
async def test_entitlement_update_validates_and_projects_safe_limits(entitlement_db):
    owner, _ = entitlement_db
    projected = await set_workspace_entitlement(owner, limits={"tournaments": 3, "stations": 2})
    assert projected["limits"]["tournaments"] == 3
    assert projected["limits"]["stations"] == 2
    with pytest.raises(ValueError):
        await set_workspace_entitlement(owner, limits={"tournaments": -1})
    with pytest.raises(ValueError):
        await set_workspace_entitlement(owner, plan_key="paid")
