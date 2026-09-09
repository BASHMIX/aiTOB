"""Manual non-payment entitlement controls are platform-admin-only and atomic."""
from __future__ import annotations

import datetime as dt
import pytest

from backend.core import database
from backend.core.entitlements import apply_manual_subscription, get_workspace_entitlement
from backend.core.storage import dbapi as aiosqlite
from backend.core.workspace_auth import hash_password


@pytest.fixture
async def entitlement_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "entitlements.sqlite"))
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_EMAIL", "platform@example.test")
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", "platform-password")
    await database.init_db()
    async with aiosqlite.connect(database.DB_PATH) as db:
        owner = await (await db.execute("SELECT id FROM users WHERE email=?", ("platform@example.test",))).fetchone()
        workspace = await (await db.execute("SELECT id FROM workspaces LIMIT 1")).fetchone()
        await db.execute(
            "INSERT INTO users (id, email, display_name, password_hash, is_platform_admin) VALUES (?, ?, ?, ?, FALSE)",
            ("non-admin", "operator@example.test", "Operator", hash_password("operator-password")),
        )
        await db.execute(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'viewer')",
            (workspace[0], "non-admin"),
        )
        await db.commit()
    yield str(owner[0]), str(workspace[0])


@pytest.mark.asyncio
async def test_platform_admin_can_activate_extend_and_suspend_without_payment(entitlement_db):
    owner_id, workspace_id = entitlement_db
    expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)).isoformat()
    activated = await apply_manual_subscription(
        workspace_id, actor_user_id=owner_id, action="activate", plan_key="managed", expires_at=expiry,
    )
    assert activated["plan_key"] == "managed"
    assert activated["status"] == "active"
    assert activated["billing_state"] == "active"

    extended = await apply_manual_subscription(
        workspace_id, actor_user_id=owner_id, action="extend", extend_days=7,
    )
    assert extended["status"] == "active"
    assert extended["expires_at"] > activated["expires_at"]

    suspended = await apply_manual_subscription(
        workspace_id, actor_user_id=owner_id, action="suspend",
    )
    assert suspended["status"] == "suspended"
    assert suspended["billing_state"] == "expired"
    async with aiosqlite.connect(database.DB_PATH) as db:
        audit = await (await db.execute(
            "SELECT action, outcome FROM audit_events WHERE workspace_id=? AND action='subscription.manual_update'",
            (workspace_id,),
        )).fetchall()
    assert len(audit) == 3
    assert all((row[0], row[1]) == ("subscription.manual_update", "accepted") for row in audit)


@pytest.mark.asyncio
async def test_non_platform_admin_and_invalid_expiry_are_rejected_without_audit(entitlement_db):
    owner_id, workspace_id = entitlement_db
    with pytest.raises(PermissionError):
        await apply_manual_subscription(
            workspace_id, actor_user_id="non-admin", action="activate", plan_key="managed",
            expires_at=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat(),
        )
    with pytest.raises(ValueError):
        await apply_manual_subscription(
            workspace_id, actor_user_id=owner_id, action="activate", plan_key="managed",
            expires_at="2030-01-01T00:00:00",
        )
    current = await get_workspace_entitlement(workspace_id)
    assert current["plan_key"] == "free"
    async with aiosqlite.connect(database.DB_PATH) as db:
        count = await (await db.execute(
            "SELECT COUNT(*) FROM audit_events WHERE workspace_id=? AND action='subscription.manual_update'",
            (workspace_id,),
        )).fetchone()
    assert count[0] == 0
