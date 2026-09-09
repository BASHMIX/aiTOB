"""Acceptance tests for the additive user/session/workspace foundation."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import uuid
from pathlib import Path

from backend.core.storage import dbapi as aiosqlite
import pytest
from fastapi.testclient import TestClient

import backend.core.database as database
from backend.api.main import app
from backend.core.workspace_auth import (
    ROLE_PERMISSIONS, authenticate_password, get_session_principal,
    legacy_owner_principal, permission_allowed,
    accept_workspace_invitation, create_workspace_invitation, cancel_workspace_invitation, disable_workspace_member,
    _totp_at, begin_totp_setup, disable_totp, enable_totp, hash_password,
    register_workspace_owner, set_workspace_member_role,
)


OWNER_EMAIL = "owner@example.test"
OWNER_PASSWORD = "a-strong-owner-password"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def isolated_workspace_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "consistent-operational-copy.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_EMAIL", OWNER_EMAIL)
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", OWNER_PASSWORD)
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_NAME", "Existing owner")
    monkeypatch.setenv("AITOB_BOOTSTRAP_WORKSPACE_NAME", "Existing owner workspace")
    monkeypatch.setenv("AITOB_AUTH_MASTER_KEY", "7lXNrOpw2HnqGYiRkqzGN70KGyxoDpcQ0H3jDXiVlvc=")
    monkeypatch.delenv("AITOB_LEGACY_HUB_PASSWORD_COMPAT", raising=False)
    run(database.init_db())
    yield db_path


def test_bootstrap_migrates_a_consistent_copy_and_is_idempotent(isolated_workspace_db: Path):
    async def verify():
        # Simulates a pre-existing operational record. Workspace scope is not
        # added in this phase, and init_db must preserve it across reruns.
        async with aiosqlite.connect(isolated_workspace_db) as db:
            await db.execute("INSERT INTO tournaments (slug, name) VALUES ('legacy-copy', 'Legacy copy')")
            await db.commit()
        await database.init_db()
        await database.init_db()
        async with aiosqlite.connect(isolated_workspace_db) as db:
            users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
            workspaces = (await (await db.execute("SELECT COUNT(*) FROM workspaces")).fetchone())[0]
            memberships = (await (await db.execute("SELECT COUNT(*) FROM workspace_memberships WHERE role='owner'")).fetchone())[0]
            tournament = await (await db.execute("SELECT name FROM tournaments WHERE slug='legacy-copy'")).fetchone()
        assert (users, workspaces, memberships) == (1, 1, 1)
        assert tournament[0] == "Legacy copy"
    run(verify())


def test_password_hash_enforces_the_documented_bootstrap_floor():
    with pytest.raises(ValueError, match="at least 10"):
        hash_password("too-short")
    encoded = hash_password("ten-chars!")
    assert encoded.startswith("scrypt$")


def test_registration_gate_invites_and_last_owner_protection(isolated_workspace_db: Path):
    async def verify():
        token, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        assert token
        with pytest.raises(PermissionError, match="disabled"):
            await register_workspace_owner("closed@example.test", "a-safe-password", "Closed", "Closed")
        invite, invite_token = await create_workspace_invitation(owner, "member@example.test", "moderator")
        assert invite["role"] == "moderator"
        member = await accept_workspace_invitation(invite_token, "member-password", "Member")
        assert member.workspace_id == owner.workspace_id
        with pytest.raises(PermissionError):
            await accept_workspace_invitation(invite_token, "member-password", "Member")
        await set_workspace_member_role(owner, member.user_id, "tournament_organizer")
        await disable_workspace_member(owner, member.user_id)
        with pytest.raises(ValueError, match="last Owner"):
            await disable_workspace_member(owner, owner.user_id)
    run(verify())


def test_public_registration_endpoint_stays_closed_and_is_rate_limited_when_enabled(
    isolated_workspace_db: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Registration is implemented but closed by default; opening it is bounded.

    This exercises the HTTP entry point rather than only the repository helper,
    so a future UI change cannot accidentally turn the public-registration gate
    into an unbounded account-creation endpoint.
    """
    client = TestClient(app)
    closed = client.post(
        "/api/session/register",
        json={
            "email": "closed-registration@example.test",
            "password": "closed-registration-password",
            "display_name": "Closed Registration",
            "workspace_name": "Closed Registration Workspace",
        },
    )
    assert closed.status_code == 403

    run(database.set_setting("ALLOW_PUBLIC_REGISTRATION", "true"))
    monkeypatch.setenv("AITOB_REGISTRATION_RATE_LIMIT", "1")
    monkeypatch.setenv("AITOB_REGISTRATION_RATE_LIMIT_WINDOW_SECONDS", "3600")
    opened = client.post(
        "/api/session/register",
        json={
            "email": "first-registration@example.test",
            "password": "first-registration-password",
            "display_name": "First Registration",
            "workspace_name": "First Registration Workspace",
        },
    )
    assert opened.status_code == 201

    limited = client.post(
        "/api/session/register",
        json={
            "email": "second-registration@example.test",
            "password": "second-registration-password",
            "display_name": "Second Registration",
            "workspace_name": "Second Registration Workspace",
        },
    )
    assert limited.status_code == 429


def test_invitation_cannot_demote_existing_owner_or_accept_wrong_password(isolated_workspace_db: Path):
    async def verify():
        _, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        _, invite_token = await create_workspace_invitation(owner, OWNER_EMAIL, "viewer")
        with pytest.raises(PermissionError):
            await accept_workspace_invitation(invite_token, "wrong-password", "Intruder")
        with pytest.raises(ValueError, match="already"):
            await accept_workspace_invitation(invite_token, OWNER_PASSWORD, "Owner")
        assert (await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD))[1].role == "owner"
    run(verify())


def test_owner_invitation_projection_is_cancellable_and_never_returns_token(isolated_workspace_db: Path):
    from backend.core.workspace_auth import list_workspace_invitations

    async def verify():
        _, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        invitation, raw_token = await create_workspace_invitation(owner, "pending@example.test", "viewer")
        visible = await list_workspace_invitations(owner)
        row = next(item for item in visible if item["id"] == invitation["id"])
        assert row["email"] == "pending@example.test"
        assert "token" not in row and "token_hash" not in row
        await cancel_workspace_invitation(owner, invitation["id"])
        cancelled = next(item for item in await list_workspace_invitations(owner) if item["id"] == invitation["id"])
        assert cancelled["cancelled_at"] is not None
        with pytest.raises(PermissionError, match="invalid or expired"):
            await accept_workspace_invitation(raw_token, "pending-password", "Pending")

    run(verify())


def test_invitation_projection_and_cancellation_are_owner_scoped(isolated_workspace_db: Path):
    async def verify():
        _, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        second_workspace = str(uuid.uuid4())
        async with aiosqlite.connect(isolated_workspace_db) as db:
            await db.execute("INSERT INTO workspaces (id,slug,name) VALUES (?,?,?)", (second_workspace, "second-invite", "Second"))
            await db.commit()
        invitation, _ = await create_workspace_invitation(owner, "one@example.test", "viewer")
        async with aiosqlite.connect(isolated_workspace_db) as db:
            await db.execute(
                "INSERT INTO workspace_invitations (id,workspace_id,email,role,token_hash,expires_at,created_by) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), second_workspace, "two@example.test", "viewer", str(uuid.uuid4()), (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat(), owner.user_id),
            )
            await db.commit()
        from backend.core.workspace_auth import list_workspace_invitations
        rows = await list_workspace_invitations(owner)
        assert {row["email"] for row in rows} == {"one@example.test"}
        with pytest.raises(ValueError, match="not found"):
            await cancel_workspace_invitation(owner, str(uuid.uuid4()))
        assert invitation["email"] == "one@example.test"

    run(verify())


def test_stale_owner_principal_cannot_invite_after_membership_disabled(isolated_workspace_db: Path):
    async def verify():
        _, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        async with aiosqlite.connect(isolated_workspace_db) as db:
            await db.execute("UPDATE workspace_memberships SET status='disabled'")
            await db.commit()
        with pytest.raises(PermissionError):
            await create_workspace_invitation(owner, "new@example.test", "viewer")
    run(verify())


def test_totp_recovery_and_replay_protection(isolated_workspace_db: Path):
    async def verify():
        _token, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        now = dt.datetime(2026, 9, 8, tzinfo=dt.timezone.utc)
        secret = await begin_totp_setup(owner, OWNER_PASSWORD, now=now)
        codes = await enable_totp(owner, secret, _totp_at(secret, int(now.timestamp() // 30)), now=now)
        with pytest.raises(PermissionError, match="Two-factor"):
            await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD, now=now + dt.timedelta(seconds=30))
        token, session = await authenticate_password(
            OWNER_EMAIL, OWNER_PASSWORD, totp_code=_totp_at(secret, int((now + dt.timedelta(seconds=30)).timestamp() // 30)),
            now=now + dt.timedelta(seconds=30),
        )
        assert token and session.user_id == owner.user_id
        # The same TOTP counter cannot be replayed. A recovery code is one-use.
        with pytest.raises(PermissionError):
            await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD, totp_code=_totp_at(secret, int((now + dt.timedelta(seconds=30)).timestamp() // 30)), now=now + dt.timedelta(seconds=30))
        await disable_totp(session, codes[0], OWNER_PASSWORD, now=now + dt.timedelta(seconds=30))
        assert (await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD))[0]
    run(verify())


def test_mfa_setup_requires_password_and_session_bound_expiring_challenge(isolated_workspace_db):
    async def verify():
        from backend.core.workspace_auth import revoke_session
        _, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        now = dt.datetime.now(dt.timezone.utc)
        with pytest.raises(PermissionError):
            await begin_totp_setup(owner, "wrong-password", now=now)
        secret = await begin_totp_setup(owner, OWNER_PASSWORD, now=now)
        _, other_session = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        code = _totp_at(secret, int(now.timestamp() // 30))
        with pytest.raises(PermissionError):
            await enable_totp(other_session, secret, code, now=now)
        with pytest.raises(PermissionError):
            later = now + dt.timedelta(minutes=11)
            await enable_totp(owner, secret, _totp_at(secret, int(later.timestamp() // 30)), now=later)
        await revoke_session(owner.session_id)
        with pytest.raises(PermissionError):
            await enable_totp(owner, secret, code, now=now)
    run(verify())


def test_login_logout_expiry_disabled_membership_and_workspace_spoof_rejection(isolated_workspace_db: Path):
    client = TestClient(app)
    response = client.post("/api/session/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    assert response.status_code == 200
    profile = response.json()
    assert profile["role"] == "owner"
    assert "password" not in response.text.lower()

    # A client supplied workspace value is ignored: principal selection comes
    # only from the session's stored membership.
    spoofed = client.get("/api/session?workspace_id=attacker-workspace")
    assert spoofed.status_code == 200
    assert spoofed.json()["workspace_id"] == profile["workspace_id"]

    assert client.post("/api/session/logout").status_code == 204
    assert client.get("/api/session").status_code == 401

    async def verify_rejections():
        token, principal = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        assert await get_session_principal(token) is not None
        async with aiosqlite.connect(isolated_workspace_db) as db:
            await db.execute("UPDATE user_sessions SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (principal.session_id,))
            await db.commit()
        assert await get_session_principal(token) is None

        async with aiosqlite.connect(isolated_workspace_db) as db:
            await db.execute("UPDATE workspace_memberships SET status='disabled' WHERE user_id=?", (principal.user_id,))
            await db.commit()
        with pytest.raises(PermissionError):
            await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
    run(verify_rejections())


def test_password_is_not_default_and_legacy_bridge_is_owner_only(isolated_workspace_db: Path, monkeypatch: pytest.MonkeyPatch):
    async def verify():
        with pytest.raises(PermissionError):
            await authenticate_password(OWNER_EMAIL, "admin")
        assert await legacy_owner_principal() is not None
        # A disabled owner removes the compatibility identity rather than
        # falling back to a globally trusted password.
        async with aiosqlite.connect(isolated_workspace_db) as db:
            await db.execute("UPDATE workspace_memberships SET status='disabled'")
            await db.commit()
        assert await legacy_owner_principal() is None
    run(verify())


def test_permission_matrix_is_explicit_and_denies_unknown_actions():
    assert permission_allowed("owner", "integrations.manage")
    assert permission_allowed("tournament_organizer", "dq.manual")
    assert not permission_allowed("stream_operator", "result.report")
    assert not permission_allowed("viewer", "match.operate")
    assert not permission_allowed("owner", "unknown.action")
    assert permission_allowed("owner", "station.manage")
    assert permission_allowed("owner", "overlay.manage")
    assert permission_allowed("owner", "conflict.manage")
    assert {"owner", "tournament_organizer", "stream_operator", "moderator", "viewer"}.issubset(ROLE_PERMISSIONS)
    # Match operations are intentionally split so a moderator can coordinate
    # attendance without gaining result, DQ, station, or configuration power.
    assert permission_allowed("moderator", "match.call")
    assert permission_allowed("moderator", "match.ready")
    assert permission_allowed("moderator", "conflict.manage")
    assert not permission_allowed("moderator", "match.start")
    assert not permission_allowed("moderator", "match.operate")
    assert permission_allowed("stream_operator", "match.stream")
    assert not permission_allowed("stream_operator", "match.call")
    assert not permission_allowed("stream_operator", "result.report")


def test_workspace_disable_refuses_inflight_work_and_revokes_after_drain(isolated_workspace_db):
    from backend.core.workspace_auth import disable_workspace

    async def verify():
        _, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        await database.upsert_active_match(
            "disable-match", workspace_id=owner.workspace_id,
            tournament_slug="disable-tournament", status="in_progress",
        )
        with pytest.raises(ValueError, match="active operations"):
            await disable_workspace(owner)
        await database.delete_active_match("disable-match", owner.workspace_id)
        await disable_workspace(owner)
        async with aiosqlite.connect(isolated_workspace_db) as db:
            workspace = await (await db.execute("SELECT status FROM workspaces WHERE id=?", (owner.workspace_id,))).fetchone()
            membership = await (await db.execute("SELECT status FROM workspace_memberships WHERE workspace_id=? AND user_id=?", (owner.workspace_id, owner.user_id))).fetchone()
            audit = await (await db.execute("SELECT action, outcome FROM audit_events WHERE workspace_id=? ORDER BY created_at DESC LIMIT 1", (owner.workspace_id,))).fetchone()
        assert workspace[0] == "disabled"
        assert membership[0] == "disabled"
        assert tuple(audit) == ("workspace.disabled", "accepted")
        assert await get_session_principal(owner.session_id) is None

    run(verify())


def test_unscoped_legacy_routes_fail_closed_for_non_owner(isolated_workspace_db: Path):
    async def add_organizer():
        async with aiosqlite.connect(isolated_workspace_db) as db:
            workspace_id = (await (await db.execute("SELECT id FROM workspaces")).fetchone())[0]
            organizer_id = str(uuid.uuid4())
            await db.execute("INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, ?)", (organizer_id, "organizer@example.test", "Organizer", hash_password("organizer-password")))
            await db.execute("INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'organizer')", (workspace_id, organizer_id))
            await db.commit()
    run(add_organizer())
    client = TestClient(app)
    assert client.post("/api/session/login", json={"email": "organizer@example.test", "password": "organizer-password"}).status_code == 200
    assert client.get("/api/settings").status_code == 403


def test_password_change_revokes_other_sessions_and_reset_is_one_use(isolated_workspace_db):
    from backend.core.workspace_auth import change_password, create_password_reset, consume_password_reset
    async def verify():
        first_token, principal = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        second_token, _ = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        await change_password(principal, OWNER_PASSWORD, "replacement-password")
        assert await get_session_principal(first_token) is not None
        assert await get_session_principal(second_token) is None
        reset = await create_password_reset(OWNER_EMAIL)
        assert reset
        await consume_password_reset(reset, "final-owner-password")
        with pytest.raises(PermissionError):
            await consume_password_reset(reset, "another-password")
        assert (await authenticate_password(OWNER_EMAIL, "final-owner-password"))[0]
    run(verify())


def test_granular_match_routes_enforce_role_boundaries(isolated_workspace_db):
    async def add_members():
        async with aiosqlite.connect(isolated_workspace_db) as db:
            workspace_id = (await (await db.execute("SELECT id FROM workspaces")).fetchone())[0]
            for role, email in (("moderator", "route-moderator@example.test"), ("stream_operator", "route-stream@example.test")):
                user_id = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO users (id,email,display_name,password_hash) VALUES (?,?,?,?)",
                    (user_id, email, role, hash_password("route-password")),
                )
                await db.execute(
                    "INSERT INTO workspace_memberships (workspace_id,user_id,role) VALUES (?,?,?)",
                    (workspace_id, user_id, role),
                )
            await db.commit()
    run(add_members())

    moderator = TestClient(app)
    assert moderator.post("/api/session/login", json={"email": "route-moderator@example.test", "password": "route-password"}).status_code == 200
    # A moderator may call/ready, but cannot submit results or change config.
    assert moderator.post("/api/active-matches/no-such-match/call").status_code == 404
    assert moderator.post("/api/active-matches/no-such-match/send").status_code == 403
    assert moderator.patch("/api/active-matches/no-such-match", json={"bot_enabled": False}).status_code == 403

    stream = TestClient(app)
    assert stream.post("/api/session/login", json={"email": "route-stream@example.test", "password": "route-password"}).status_code == 200
    # Stream operators can use stream controls, but never call or report scores.
    assert stream.post("/api/active-matches/no-such-match/toggle-stream", json={"is_stream_match": True}).status_code == 404
    assert stream.post("/api/active-matches/no-such-match/call").status_code == 403
    assert stream.post("/api/active-matches/no-such-match/send").status_code == 403


def test_email_verification_token_is_hashed_expiring_and_one_use(isolated_workspace_db):
    from backend.core.workspace_auth import create_email_verification, consume_email_verification
    async def verify():
        _, principal = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        token = await create_email_verification(principal)
        async with aiosqlite.connect(isolated_workspace_db) as db:
            row = await (await db.execute("SELECT token_hash FROM email_verification_tokens")).fetchone()
            assert row[0] != token
        await consume_email_verification(token)
        with pytest.raises(PermissionError):
            await consume_email_verification(token)
    run(verify())


def test_auth_rate_limit_is_database_backed_and_resets_after_window(isolated_workspace_db):
    from backend.core.workspace_auth import enforce_auth_rate_limit

    async def verify():
        started = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        await enforce_auth_rate_limit("login", "client:owner", limit=2, window_seconds=60, now=started)
        await enforce_auth_rate_limit("login", "client:owner", limit=2, window_seconds=60, now=started)
        with pytest.raises(PermissionError, match="Too many"):
            await enforce_auth_rate_limit("login", "client:owner", limit=2, window_seconds=60, now=started)
        await enforce_auth_rate_limit(
            "login", "client:owner", limit=2, window_seconds=60,
            now=started + dt.timedelta(seconds=61),
        )

    run(verify())


def test_two_workspaces_can_use_same_station_public_id_without_cross_access(isolated_workspace_db):
    async def verify():
        async with aiosqlite.connect(isolated_workspace_db) as db:
            first_workspace = (await (await db.execute("SELECT id FROM workspaces")).fetchone())[0]
            second_workspace = str(uuid.uuid4())
            await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, 'second', 'Second')", (second_workspace,))
            await db.commit()
        await database.create_station("main", "First main", first_workspace)
        await database.create_station("main", "Second main", second_workspace)
        first = await database.get_stations(first_workspace)
        second = await database.get_stations(second_workspace)
        assert [(row["id"], row["name"]) for row in first] == [("main", "First main")]
        assert [(row["id"], row["name"]) for row in second] == [("main", "Second main")]
        await database.update_station("main", workspace_id=second_workspace, name="Second renamed")
        assert (await database.get_stations(first_workspace))[0]["name"] == "First main"
        assert (await database.get_stations(second_workspace))[0]["name"] == "Second renamed"

    run(verify())


def test_hub_command_claim_is_atomic_and_owner_checked(isolated_workspace_db):
    async def verify():
        await database.add_hub_command("call_match one", workspace_id="workspace-one")
        first, second = await asyncio.gather(
            database.claim_pending_hub_commands("worker-a", limit=1),
            database.claim_pending_hub_commands("worker-b", limit=1),
        )
        claimed = first + second
        assert len(claimed) == 1
        owner = "worker-a" if first else "worker-b"
        assert not await database.finish_hub_command(claimed[0]["id"], "other-worker", "done")
        assert await database.finish_hub_command(claimed[0]["id"], owner, "done")

    run(verify())


def test_overlay_link_is_workspace_scoped_hashed_and_revocable(isolated_workspace_db):
    from backend.core.overlay_access import issue_overlay_access, resolve_overlay_access, revoke_overlay_access

    async def verify():
        _, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        await database.create_station("broadcast", "Broadcast", owner.workspace_id)
        token_id, token = await issue_overlay_access(owner.workspace_id, "broadcast", owner.user_id)
        assert (await resolve_overlay_access(token, "broadcast"))["workspace_id"] == owner.workspace_id
        async with aiosqlite.connect(isolated_workspace_db) as db:
            stored = await (await db.execute("SELECT token_hash FROM overlay_access_tokens WHERE id=?", (token_id,))).fetchone()
        assert stored and stored[0] != token
        assert await revoke_overlay_access(owner.workspace_id, token_id)
        assert await resolve_overlay_access(token, "broadcast") is None

    run(verify())


def test_managed_asset_deletion_refuses_workspace_overlay_config_reference(isolated_workspace_db):
    """An owned upload remains undeletable while an overlay preset uses it.

    Overlay JSON is intentionally flexible, so this covers both the canonical
    ``background_url`` and a nested image element source.  A guarded deletion
    must examine the saved preset rather than only player/match projections.
    """
    async def verify():
        _, owner = await authenticate_password(OWNER_EMAIL, OWNER_PASSWORD)
        asset = await database.record_media_asset(
            workspace_id=owner.workspace_id,
            asset_type="overlay_asset",
            owner_type="workspace",
            owner_id=owner.workspace_id,
            storage_url="/static/assets/workspace-logo.png",
            storage_key="workspace-logo.png",
        )
        await database.save_overlay(
            "broadcast-layout",
            {
                "background_url": "/static/assets/workspace-logo.png",
                "elements": {},
            },
            owner.workspace_id,
        )
        with pytest.raises(ValueError, match="referenced"):
            await database.delete_media_asset(asset["id"], owner.workspace_id)

            await database.save_overlay(
                "broadcast-layout-nested",
                {"elements": {"sponsor": {"type": "image", "src": "/static/assets/workspace-logo.png"}}},
                owner.workspace_id,
            )
        with pytest.raises(ValueError, match="referenced"):
            await database.delete_media_asset(asset["id"], owner.workspace_id)

        await database.save_overlay("broadcast-layout", {"elements": {}}, owner.workspace_id)
        assert await database.delete_media_asset(asset["id"], owner.workspace_id)

    run(verify())
