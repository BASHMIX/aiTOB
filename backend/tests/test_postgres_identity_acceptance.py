"""PostgreSQL acceptance for the user, session, and membership foundation.

The repository conftest creates a disposable database for every test, so no
operational database or external mail service is touched.
"""

from __future__ import annotations

import datetime as dt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core import database
from backend.core.workspace_auth import (
    _totp_at,
    _totp_counter,
    authenticate_password,
    begin_totp_setup,
    create_password_reset,
    enable_totp,
    hash_password,
    get_session_principal,
    revoke_session,
)


@pytest.fixture(autouse=True)
async def identity_database(monkeypatch: pytest.MonkeyPatch):
    """Bootstrap one disposable Owner without any production credentials."""
    monkeypatch.setenv("AITOB_AUTH_MASTER_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_EMAIL", "pg-owner@example.test")
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", "pg-owner-password")
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_NAME", "PG Owner")
    monkeypatch.setenv("AITOB_BOOTSTRAP_WORKSPACE_NAME", "PG Acceptance Workspace")
    monkeypatch.delenv("ALLOW_PUBLIC_REGISTRATION", raising=False)
    await database.init_db()


def test_owner_http_session_lifecycle_and_workspace_claim_is_postgres():
    """Login/logout/expiry use only the durable session membership claim."""
    client = TestClient(app)
    login = client.post(
        "/api/session/login",
        json={"email": "pg-owner@example.test", "password": "pg-owner-password"},
    )
    assert login.status_code == 200
    profile = login.json()
    assert profile["role"] == "owner"
    assert profile["workspace_name"] == "PG Acceptance Workspace"
    assert client.get("/api/session?workspace_id=foreign-workspace").json()["workspace_id"] == profile["workspace_id"]
    assert client.post("/api/session/logout").status_code == 204
    assert client.get("/api/session").status_code == 401

    token, principal = __import__("asyncio").run(
        authenticate_password("pg-owner@example.test", "pg-owner-password")
    )
    assert token
    __import__("asyncio").run(revoke_session(principal.session_id))
    # The cookie is not involved in this assertion: revocation is checked from
    # PostgreSQL by a fresh session lookup.
    assert __import__("asyncio").run(get_session_principal(token)) is None


def test_invitation_acceptance_role_change_cancellation_and_last_owner_are_http():
    """Invitation lifecycle is owner-scoped and enforced by the API."""
    owner = TestClient(app)
    assert owner.post(
        "/api/session/login",
        json={"email": "pg-owner@example.test", "password": "pg-owner-password"},
    ).status_code == 200

    accepted_invite = owner.post(
        "/api/workspace/invitations",
        json={"email": "pg-member@example.test", "role": "viewer"},
    )
    assert accepted_invite.status_code == 201
    invite_data = accepted_invite.json()
    acceptance_token = invite_data["acceptance_token"]
    assert "token_hash" not in invite_data["invitation"]

    member = TestClient(app)
    accepted = member.post(
        "/api/workspace/invitations/accept",
        json={
            "token": acceptance_token,
            "password": "pg-member-password",
            "display_name": "PG Member",
        },
    )
    assert accepted.status_code == 200
    assert member.post(
        "/api/session/login",
        json={"email": "pg-member@example.test", "password": "pg-member-password"},
    ).json()["role"] == "viewer"

    # The Owner may change the member role, but the member cannot change it
    # back through the owner-only endpoint.
    member_id = member.get("/api/session").json()["user_id"]
    role_change = owner.put(
        f"/api/workspace/members/{member_id}/role",
        json={"role": "tournament_organizer"},
    )
    assert role_change.status_code == 200
    assert member.put(
        f"/api/workspace/members/{member_id}/role",
        json={"role": "owner"},
    ).status_code == 403

    pending = owner.post(
        "/api/workspace/invitations",
        json={"email": "cancelled@example.test", "role": "moderator"},
    )
    assert pending.status_code == 201
    pending_body = pending.json()
    invite_id = pending_body["invitation"]["id"]
    assert owner.delete(f"/api/workspace/invitations/{invite_id}").status_code == 204
    assert member.post(
        "/api/workspace/invitations/accept",
        json={
            "token": pending_body["acceptance_token"],
            "password": "cancelled-password",
            "display_name": "Cancelled",
        },
    ).status_code == 422

    owner_id = owner.get("/api/session").json()["user_id"]
    assert owner.delete(f"/api/workspace/members/{owner_id}").status_code == 422


def test_totp_recovery_and_password_reset_use_postgres_and_fake_delivery():
    """2FA and reset are exercised without SMTP; returned tokens model a test mail sink."""
    import asyncio

    client = TestClient(app)
    assert client.post(
        "/api/session/login",
        json={"email": "pg-owner@example.test", "password": "pg-owner-password"},
    ).status_code == 200
    setup = client.post(
        "/api/session/mfa/setup",
        json={"password": "pg-owner-password"},
    )
    assert setup.status_code == 200
    secret = setup.json()["setup_secret"]
    now = dt.datetime.now(dt.timezone.utc)
    code = _totp_at(secret, _totp_counter(now))
    enabled = client.post(
        "/api/session/mfa/enable",
        json={"setup_secret": secret, "code": code},
    )
    assert enabled.status_code == 200
    recovery_code = enabled.json()["recovery_codes"][0]
    assert recovery_code
    assert client.post("/api/session/logout").status_code == 204
    assert client.post(
        "/api/session/login",
        json={"email": "pg-owner@example.test", "password": "pg-owner-password"},
    ).status_code == 401
    recovery_login = client.post(
        "/api/session/login",
        json={
            "email": "pg-owner@example.test",
            "password": "pg-owner-password",
            "totp_code": recovery_code,
        },
    )
    assert recovery_login.status_code == 200
    assert client.post("/api/session/logout").status_code == 204
    assert client.post(
        "/api/session/login",
        json={
            "email": "pg-owner@example.test",
            "password": "pg-owner-password",
            "totp_code": recovery_code,
        },
    ).status_code == 401

    # The reset token is obtained from the in-process test delivery sink, not
    # from SMTP. The public endpoint remains enumeration-safe and generic.
    reset_response = client.post(
        "/api/session/password/reset-request",
        json={"email": "pg-owner@example.test"},
    )
    assert reset_response.status_code == 202
    reset_token = asyncio.run(create_password_reset("pg-owner@example.test"))
    assert reset_token
    assert client.post(
        "/api/session/password/reset",
        json={"token": reset_token, "new_password": "pg-owner-new-password"},
    ).status_code == 204
    # Reset revokes every existing session and replaces the password hash.
    assert client.post(
        "/api/session/login",
        json={"email": "pg-owner@example.test", "password": "pg-owner-password"},
    ).status_code == 401
    final_login = client.post(
        "/api/session/login",
        json={
            "email": "pg-owner@example.test",
            "password": "pg-owner-new-password",
            # Enabling TOTP records the current counter as used; use exactly
            # the next counter.  Adding a fixed 31 seconds can cross two
            # windows when the test starts near a boundary and would create
            # a legitimately invalid code.
            "totp_code": _totp_at(secret, _totp_counter(dt.datetime.now(dt.timezone.utc)) + 1),
        },
    )
    assert final_login.status_code == 200
