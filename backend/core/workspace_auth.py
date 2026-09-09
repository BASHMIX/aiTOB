"""Trusted users, memberships, and revocable sessions for aiTOB.

Existing tournament/integration records are intentionally not scoped here. This
additive foundation gives later ownership migrations one authenticated source
of truth without accepting a workspace identifier from the client.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from typing import Final
from cryptography.fernet import Fernet, InvalidToken

from backend.core.storage import dbapi as aiosqlite, is_postgres

from backend.core import database

SESSION_COOKIE: Final = "aitob_session"
ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "owner": frozenset({
        "workspace.read", "workspace.manage", "settings.manage",
        "integrations.manage", "tournament.manage", "match.operate",
        "result.report", "dq.manual", "proposal.review",
        "station.manage", "overlay.manage", "conflict.manage",
    }),
    "tournament_organizer": frozenset({"workspace.read", "settings.manage", "tournament.manage", "match.operate", "result.report", "dq.manual", "proposal.review"}),
    "stream_operator": frozenset({"workspace.read", "station.manage", "overlay.manage"}),
    "moderator": frozenset({"workspace.read", "match.operate", "conflict.manage"}),
    "viewer": frozenset({"workspace.read"}),
    # Legacy rows are mapped explicitly during the staged ownership migration;
    # they remain aliases only until the final role normalization is applied.
    "organizer": frozenset({"workspace.read", "settings.manage", "tournament.manage", "match.operate", "result.report", "dq.manual", "proposal.review"}),
    "operator": frozenset({"workspace.read", "station.manage", "overlay.manage"}),
}


@dataclass(frozen=True)
class SessionPrincipal:
    user_id: str
    workspace_id: str
    role: str
    session_id: str | None
    legacy: bool = False


def permission_allowed(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_timestamp(value: str | dt.datetime) -> dt.datetime:
    parsed = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed.astimezone(dt.timezone.utc)


def hash_password(password: str) -> str:
    # This is the documented local bootstrap floor.  The hash remains scrypt;
    # deployment can enforce a stricter password policy at the account UI.
    if not isinstance(password, str) or len(password) < 10:
        raise ValueError("Password must contain at least 10 characters")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "$".join(("scrypt", "16384", "8", "1", base64.urlsafe_b64encode(salt).decode("ascii"), base64.urlsafe_b64encode(derived).decode("ascii")))


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, expected_b64 = encoded.split("$")
        if algorithm != "scrypt":
            return False
        expected = base64.urlsafe_b64decode(expected_b64.encode("ascii"))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=base64.urlsafe_b64decode(salt_b64.encode("ascii")), n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (AttributeError, ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def enforce_auth_rate_limit(
    action: str,
    subject: str,
    *,
    limit: int,
    window_seconds: int,
    now: dt.datetime | None = None,
) -> None:
    """Database-backed fixed-window limiter shared by every API process."""
    observed = now or _utcnow()
    subject_hash = _token_hash(subject.strip().lower())
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            suffix = " FOR UPDATE" if is_postgres() else ""
            row = await (await db.execute(
                "SELECT window_started_at, attempt_count FROM auth_rate_limits "
                "WHERE action=? AND subject_hash=?" + suffix,
                (action, subject_hash),
            )).fetchone()
            reset = not row or (observed - _parse_timestamp(row[0])).total_seconds() >= window_seconds
            if reset:
                await db.execute(
                    """INSERT INTO auth_rate_limits (action, subject_hash, window_started_at, attempt_count)
                       VALUES (?, ?, ?, 1)
                       ON CONFLICT(action, subject_hash) DO UPDATE SET
                         window_started_at=EXCLUDED.window_started_at, attempt_count=1""",
                    (action, subject_hash, observed.isoformat()),
                )
            elif int(row[1]) >= limit:
                raise PermissionError("Too many attempts. Try again later.")
            else:
                await db.execute(
                    "UPDATE auth_rate_limits SET attempt_count=attempt_count+1 WHERE action=? AND subject_hash=?",
                    (action, subject_hash),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise


def _auth_box() -> Fernet:
    key = os.getenv("AITOB_AUTH_MASTER_KEY", "").strip()
    if not key:
        raise RuntimeError("Authentication encryption master key is unavailable.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Authentication encryption master key is invalid.") from exc


def _totp_at(secret: str, counter: int) -> str:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    digest = hmac.new(base64.b32decode(padded), counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def _totp_counter(now: dt.datetime | None = None) -> int:
    value = now or _utcnow()
    return int(value.timestamp() // 30)


async def has_mfa(user_id: str) -> bool:
    async with aiosqlite.connect(database.DB_PATH) as db:
        row = await (await db.execute("SELECT 1 FROM user_mfa_credentials WHERE user_id=?", (user_id,))).fetchone()
    return bool(row)


async def _require_account_session(db, principal: SessionPrincipal, *, now=None, password=None):
    if not principal.session_id or principal.legacy:
        raise PermissionError("An active account session is required.")
    lock = " FOR UPDATE OF u" if is_postgres() else ""
    row = await (await db.execute(
        """SELECT u.password_hash, s.expires_at FROM users u
           JOIN user_sessions s ON s.user_id=u.id
           JOIN workspace_memberships m ON m.user_id=u.id AND m.workspace_id=s.workspace_id
           JOIN workspaces w ON w.id=m.workspace_id
           WHERE u.id=? AND s.id=? AND s.workspace_id=? AND s.revoked_at IS NULL
             AND u.status='active' AND m.status='active' AND w.status='active'""" + lock,
        (principal.user_id, principal.session_id, principal.workspace_id),
    )).fetchone()
    if not row or _parse_timestamp(row[1]) <= (now or _utcnow()):
        raise PermissionError("An active account session is required.")
    if password is not None and not verify_password(password, row[0]):
        raise PermissionError("Password confirmation failed.")


async def begin_totp_setup(principal: SessionPrincipal, password: str, *, now=None) -> str:
    """Password-confirmed, session-bound encrypted setup expires in ten minutes."""
    issued = now or _utcnow()
    secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    ciphertext = _auth_box().encrypt(secret.encode("ascii")).decode("ascii")
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        await _require_account_session(db, principal, now=issued, password=password)
        if await (await db.execute("SELECT 1 FROM user_mfa_credentials WHERE user_id=?", (principal.user_id,))).fetchone():
            raise ValueError("Two-factor authentication is already enabled.")
        await db.execute(
            """INSERT INTO user_mfa_setup (user_id, session_id, encrypted_secret, expires_at) VALUES (?, ?, ?, ?)
               ON CONFLICT (user_id) DO UPDATE SET session_id=EXCLUDED.session_id,
                 encrypted_secret=EXCLUDED.encrypted_secret, expires_at=EXCLUDED.expires_at""",
            (principal.user_id, principal.session_id, ciphertext, (issued + dt.timedelta(minutes=10)).isoformat()),
        )
        await db.commit()
    return secret


async def enable_totp(principal: SessionPrincipal, secret: str, code: str, *, now: dt.datetime | None = None) -> list[str]:
    counter = _totp_counter(now)
    if not hmac.compare_digest(_totp_at(secret, counter), str(code).strip()):
        raise PermissionError("Invalid authenticator code.")
    recovery_codes = [secrets.token_urlsafe(8) for _ in range(8)]
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await _require_account_session(db, principal, now=now)
            setup = await (await db.execute(
                "SELECT encrypted_secret, expires_at FROM user_mfa_setup WHERE user_id=? AND session_id=?",
                (principal.user_id, principal.session_id),
            )).fetchone()
            if not setup or _parse_timestamp(setup[1]) <= (now or _utcnow()):
                raise PermissionError("Authenticator setup expired or belongs to another session.")
            try:
                stored_secret = _auth_box().decrypt(setup[0].encode("ascii")).decode("ascii")
            except (InvalidToken, UnicodeError):
                raise PermissionError("Authenticator setup is unavailable.") from None
            if not hmac.compare_digest(stored_secret, secret):
                raise PermissionError("Authenticator setup does not match.")
            existing = await (await db.execute("SELECT 1 FROM user_mfa_credentials WHERE user_id=?", (principal.user_id,))).fetchone()
            if existing:
                raise ValueError("Two-factor authentication is already enabled.")
            ciphertext = _auth_box().encrypt(secret.encode("ascii")).decode("ascii")
            await db.execute(
                "INSERT INTO user_mfa_credentials (user_id, encrypted_totp_secret, last_verified_counter) VALUES (?, ?, ?)",
                (principal.user_id, ciphertext, counter),
            )
            for recovery in recovery_codes:
                await db.execute(
                    "INSERT INTO user_recovery_codes (id, user_id, code_hash) VALUES (?, ?, ?)",
                    (str(uuid.uuid4()), principal.user_id, _token_hash(recovery)),
                )
            await db.execute("DELETE FROM user_mfa_setup WHERE user_id=?", (principal.user_id,))
            await db.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND id<>?", (principal.user_id, principal.session_id))
            await db.commit()
        except Exception:
            await db.rollback(); raise
    return recovery_codes


async def _consume_mfa_code(db, user_id: str, code: str, *, now: dt.datetime | None = None) -> bool:
    record = await (await db.execute(
        "SELECT encrypted_totp_secret, last_verified_counter FROM user_mfa_credentials WHERE user_id=?", (user_id,)
    )).fetchone()
    if not record:
        return True
    candidate = str(code or "").strip()
    recovery = await (await db.execute(
        "SELECT id FROM user_recovery_codes WHERE user_id=? AND code_hash=? AND used_at IS NULL", (user_id, _token_hash(candidate))
    )).fetchone()
    if recovery:
        consumed = await db.execute("UPDATE user_recovery_codes SET used_at=CURRENT_TIMESTAMP WHERE id=? AND used_at IS NULL", (recovery[0],))
        return consumed.rowcount == 1
    try:
        secret = _auth_box().decrypt(str(record[0]).encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise RuntimeError("Two-factor authentication secret cannot be read.") from exc
    now_counter = _totp_counter(now)
    previous = int(record[1]) if record[1] is not None else -1
    for counter in (now_counter - 1, now_counter, now_counter + 1):
        if counter <= previous:
            continue
        if hmac.compare_digest(_totp_at(secret, counter), candidate):
            updated = await db.execute(
                "UPDATE user_mfa_credentials SET last_verified_counter=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND (last_verified_counter IS NULL OR last_verified_counter<?)",
                (counter, user_id, counter),
            )
            return updated.rowcount == 1
    return False


async def disable_totp(principal: SessionPrincipal, code: str, password: str, *, now: dt.datetime | None = None) -> None:
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await _require_account_session(db, principal, password=password, now=now)
            if not await _consume_mfa_code(db, principal.user_id, code, now=now):
                raise PermissionError("Invalid authenticator or recovery code.")
            await db.execute("DELETE FROM user_recovery_codes WHERE user_id=?", (principal.user_id,))
            await db.execute("DELETE FROM user_mfa_credentials WHERE user_id=?", (principal.user_id,))
            await db.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND id<>? AND revoked_at IS NULL", (principal.user_id, principal.session_id or ""))
            await db.commit()
        except Exception:
            await db.rollback(); raise


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:64] or "owner-workspace"


MEMBER_ROLES: Final[frozenset[str]] = frozenset({
    "owner", "tournament_organizer", "stream_operator", "moderator", "viewer",
})


async def _lock_workspace(db, workspace_id: str) -> None:
    suffix = " FOR UPDATE" if is_postgres() else ""
    row = await (await db.execute(
        "SELECT id FROM workspaces WHERE id=? AND status='active'" + suffix,
        (workspace_id,),
    )).fetchone()
    if not row:
        raise PermissionError("Workspace is unavailable.")


async def _require_current_owner(db, principal: SessionPrincipal) -> None:
    # Serializes membership changes, including two Owners trying to demote
    # each other. Re-read the actor after acquiring the workspace row lock.
    await _lock_workspace(db, principal.workspace_id)
    row = await (await db.execute(
        "SELECT m.role FROM workspace_memberships m JOIN users u ON u.id=m.user_id "
        "WHERE m.workspace_id=? AND m.user_id=? AND m.status='active' AND u.status='active'",
        (principal.workspace_id, principal.user_id),
    )).fetchone()
    if not row or row[0] != "owner":
        raise PermissionError("Only a current Owner may manage members.")


def _invite_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, _token_hash(token)


async def public_registration_enabled() -> bool:
    async with aiosqlite.connect(database.DB_PATH) as db:
        row = await (await db.execute(
            "SELECT value FROM global_settings WHERE key='ALLOW_PUBLIC_REGISTRATION'"
        )).fetchone()
    return bool(row and str(row[0]).lower() == "true")


async def register_workspace_owner(email: str, password: str, display_name: str, workspace_name: str) -> SessionPrincipal:
    """Create an Owner only when the explicitly-disabled-by-default gate is open."""
    if not await public_registration_enabled():
        raise PermissionError("Public registration is disabled.")
    normalized_email = email.strip().lower()
    if "@" not in normalized_email or not display_name.strip() or not workspace_name.strip():
        raise ValueError("Valid account and workspace details are required.")
    user_id, workspace_id = str(uuid.uuid4()), str(uuid.uuid4())
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            existing = await (await db.execute("SELECT id FROM users WHERE email=?", (normalized_email,))).fetchone()
            if existing:
                raise ValueError("Email is already registered.")
            slug_base = _safe_slug(workspace_name)
            slug = slug_base
            suffix = 2
            while await (await db.execute("SELECT 1 FROM workspaces WHERE slug=?", (slug,))).fetchone():
                slug = f"{slug_base[:58]}-{suffix}"; suffix += 1
            await db.execute(
                "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, ?)",
                (user_id, normalized_email, display_name.strip()[:120], hash_password(password)),
            )
            await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (workspace_id, slug, workspace_name.strip()[:120]))
            await db.execute("INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner')", (workspace_id, user_id))
            await db.execute(
                "INSERT INTO workspace_entitlements (workspace_id, plan_key, billing_state) VALUES (?, 'free', 'non_billed')",
                (workspace_id,),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return SessionPrincipal(user_id, workspace_id, "owner", None)


async def create_workspace_invitation(
    principal: SessionPrincipal, email: str, role: str, *, now: dt.datetime | None = None,
) -> tuple[dict[str, str], str]:
    if principal.role != "owner":
        raise PermissionError("Only an Owner may invite members.")
    if role not in MEMBER_ROLES - {"owner"}:
        raise ValueError("Invitation role is invalid.")
    normalized_email = email.strip().lower()
    if "@" not in normalized_email:
        raise ValueError("A valid invitation email is required.")
    issued = now or _utcnow()
    token, token_hash = _invite_token()
    invite_id = str(uuid.uuid4())
    expires_at = issued + dt.timedelta(days=7)
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await _require_current_owner(db, principal)
            await db.execute(
                "UPDATE workspace_invitations SET cancelled_at=? WHERE workspace_id=? AND email=? AND accepted_at IS NULL AND cancelled_at IS NULL",
                (issued.isoformat(), principal.workspace_id, normalized_email),
            )
            await db.execute(
                """INSERT INTO workspace_invitations (id, workspace_id, email, role, token_hash, expires_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (invite_id, principal.workspace_id, normalized_email, role, token_hash, expires_at.isoformat(), principal.user_id),
            )
            await db.commit()
        except Exception:
            await db.rollback(); raise
    return {"id": invite_id, "email": normalized_email, "role": role, "expires_at": expires_at.isoformat()}, token


async def list_workspace_members(principal: SessionPrincipal) -> list[dict]:
    async with aiosqlite.connect(database.DB_PATH) as db:
        await _require_current_owner(db, principal)
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            """SELECT u.id,u.email,u.display_name,m.role,m.status,m.created_at
               FROM workspace_memberships m JOIN users u ON u.id=m.user_id
               WHERE m.workspace_id=? ORDER BY m.created_at""", (principal.workspace_id,),
        )).fetchall()
    return [dict(row) for row in rows]


async def cancel_workspace_invitation(principal: SessionPrincipal, invitation_id: str) -> None:
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await _require_current_owner(db, principal)
            result = await db.execute(
                """UPDATE workspace_invitations SET cancelled_at=CURRENT_TIMESTAMP
                   WHERE id=? AND workspace_id=? AND accepted_at IS NULL AND cancelled_at IS NULL""",
                (invitation_id, principal.workspace_id),
            )
            if result.rowcount != 1:
                raise ValueError("Pending invitation was not found.")
            await db.commit()
        except Exception:
            await db.rollback(); raise


async def accept_workspace_invitation(token: str, password: str, display_name: str, *, totp_code: str | None = None, now: dt.datetime | None = None) -> SessionPrincipal:
    if not token or not display_name.strip():
        raise ValueError("Invitation and display name are required.")
    issued = now or _utcnow()
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            invite = await (await db.execute(
                "SELECT * FROM workspace_invitations WHERE token_hash=? AND accepted_at IS NULL AND cancelled_at IS NULL",
                (_token_hash(token),),
            )).fetchone()
            if not invite or _parse_timestamp(invite["expires_at"]) <= issued:
                raise PermissionError("Invitation is invalid or expired.")
            await _lock_workspace(db, str(invite["workspace_id"]))
            # Conditional consumption is atomic across separate connections.
            claimed = await db.execute(
                "UPDATE workspace_invitations SET accepted_at=? WHERE id=? AND accepted_at IS NULL AND cancelled_at IS NULL",
                (issued.isoformat(), invite["id"]),
            )
            if claimed.rowcount != 1:
                raise PermissionError("Invitation is invalid or expired.")
            existing = await (await db.execute("SELECT id, status, password_hash FROM users WHERE email=?", (invite["email"],))).fetchone()
            if existing:
                if existing["status"] != "active" or not verify_password(password, existing["password_hash"]):
                    raise PermissionError("Account authentication is required.")
                user_id = str(existing["id"])
                if not await _consume_mfa_code(db, user_id, totp_code or "", now=issued):
                    raise PermissionError("Two-factor authentication is required.")
                membership = await (await db.execute(
                    "SELECT 1 FROM workspace_memberships WHERE workspace_id=? AND user_id=?",
                    (invite["workspace_id"], user_id),
                )).fetchone()
                if membership:
                    raise ValueError("Membership already exists; use member management.")
            else:
                user_id = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, ?)",
                    (user_id, invite["email"], display_name.strip()[:120], hash_password(password)),
                )
            await db.execute(
                "INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, ?)",
                (invite["workspace_id"], user_id, invite["role"]),
            )
            await db.execute("UPDATE workspace_invitations SET accepted_at=? WHERE id=?", (issued.isoformat(), invite["id"]))
            await db.commit()
        except Exception:
            await db.rollback(); raise
    return SessionPrincipal(user_id, str(invite["workspace_id"]), str(invite["role"]), None)


async def set_workspace_member_role(principal: SessionPrincipal, user_id: str, role: str) -> None:
    if principal.role != "owner":
        raise PermissionError("Only an Owner may change roles.")
    if role not in MEMBER_ROLES:
        raise ValueError("Role is invalid.")
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await _require_current_owner(db, principal)
            current = await (await db.execute(
                "SELECT role FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active'",
                (principal.workspace_id, user_id),
            )).fetchone()
            if not current:
                raise ValueError("Active membership was not found.")
            if current[0] == "owner" and role != "owner":
                owners = await (await db.execute(
                    "SELECT count(*) FROM workspace_memberships WHERE workspace_id=? AND role='owner' AND status='active'",
                    (principal.workspace_id,),
                )).fetchone()
                if int(owners[0]) <= 1:
                    raise ValueError("The last Owner cannot be demoted.")
            await db.execute(
                "UPDATE workspace_memberships SET role=?, updated_at=CURRENT_TIMESTAMP WHERE workspace_id=? AND user_id=?",
                (role, principal.workspace_id, user_id),
            )
            await db.commit()
        except Exception:
            await db.rollback(); raise


async def disable_workspace_member(principal: SessionPrincipal, user_id: str) -> None:
    if principal.role != "owner":
        raise PermissionError("Only an Owner may remove members.")
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await _require_current_owner(db, principal)
            row = await (await db.execute(
                "SELECT role FROM workspace_memberships WHERE workspace_id=? AND user_id=? AND status='active'",
                (principal.workspace_id, user_id),
            )).fetchone()
            if not row:
                raise ValueError("Active membership was not found.")
            if row[0] == "owner":
                owners = await (await db.execute(
                    "SELECT count(*) FROM workspace_memberships WHERE workspace_id=? AND role='owner' AND status='active'",
                    (principal.workspace_id,),
                )).fetchone()
                if int(owners[0]) <= 1:
                    raise ValueError("The last Owner cannot be removed.")
            await db.execute(
                "UPDATE workspace_memberships SET status='disabled', updated_at=CURRENT_TIMESTAMP WHERE workspace_id=? AND user_id=?",
                (principal.workspace_id, user_id),
            )
            await db.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND workspace_id=? AND revoked_at IS NULL", (user_id, principal.workspace_id))
            await db.commit()
        except Exception:
            await db.rollback(); raise


async def bootstrap_initial_owner_from_env() -> bool:
    """Create one owner from explicit bootstrap config, or do nothing.

    There is no HTTP bootstrap endpoint and no default credential.  Any existing
    user prevents a second implicit workspace or owner from being created.
    """
    email = os.getenv("AITOB_BOOTSTRAP_OWNER_EMAIL", "").strip().lower()
    password = os.getenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", "")
    display_name = os.getenv("AITOB_BOOTSTRAP_OWNER_NAME", "").strip() or "Owner"
    workspace_name = os.getenv("AITOB_BOOTSTRAP_WORKSPACE_NAME", "").strip() or f"{display_name} workspace"
    if not email and not password:
        return False
    if not email or not password:
        raise RuntimeError("Owner bootstrap needs both AITOB_BOOTSTRAP_OWNER_EMAIL and AITOB_BOOTSTRAP_OWNER_PASSWORD")
    if "@" not in email or password.lower() == "admin":
        raise RuntimeError("Owner bootstrap values are invalid")

    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        user_id, workspace_id = str(uuid.uuid4()), str(uuid.uuid4())
        slug = _safe_slug(os.getenv("AITOB_BOOTSTRAP_WORKSPACE_SLUG", "") or workspace_name)
        await db.execute("BEGIN IMMEDIATE")
        try:
            if is_postgres():
                # Serializes bootstrap across API/bot processes before rows
                # exist. BEGIN alone cannot lock an absent owner record.
                await db.execute("SELECT pg_advisory_xact_lock(734102901)")
            existing = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
            if int(existing[0]):
                await db.rollback()
                return False
            await db.execute("INSERT INTO users (id, email, display_name, password_hash, is_platform_admin) VALUES (?, ?, ?, ?, TRUE)", (user_id, email, display_name[:120], hash_password(password)))
            await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", (workspace_id, slug, workspace_name[:120]))
            await db.execute("INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner')", (workspace_id, user_id))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return True


async def authenticate_password(email: str, password: str, *, totp_code: str | None = None, now: dt.datetime | None = None) -> tuple[str, SessionPrincipal]:
    now = now or _utcnow()
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, password_hash, status FROM users WHERE email=?", (email.strip().lower(),)) as cursor:
            user = await cursor.fetchone()
        if not user or user["status"] != "active" or not verify_password(password, user["password_hash"]):
            raise PermissionError("Invalid email or password")
        async with db.execute(
            """SELECT m.workspace_id, m.role FROM workspace_memberships m JOIN workspaces w ON w.id=m.workspace_id
               WHERE m.user_id=? AND m.status='active' AND w.status='active' ORDER BY m.created_at""", (user["id"],)
        ) as cursor:
            memberships = await cursor.fetchall()
        # This foundation exposes no workspace selection; rejecting ambiguity is
        # safer than allowing a caller-supplied workspace identifier.
        if len(memberships) != 1:
            raise PermissionError("Account does not have exactly one active workspace")
        membership = memberships[0]
        mfa_enabled = await (await db.execute("SELECT 1 FROM user_mfa_credentials WHERE user_id=?", (user["id"],))).fetchone()
        if mfa_enabled:
            await db.execute("BEGIN IMMEDIATE")
            try:
                if not await _consume_mfa_code(db, str(user["id"]), totp_code or "", now=now):
                    raise PermissionError("Two-factor authentication code is required.")
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        ttl_hours = int(os.getenv("AITOB_SESSION_TTL_HOURS", "12"))
        if not 1 <= ttl_hours <= 24 * 31:
            raise RuntimeError("AITOB_SESSION_TTL_HOURS must be between 1 and 744")
        token, session_id = secrets.token_urlsafe(32), str(uuid.uuid4())
        expires_at = now + dt.timedelta(hours=ttl_hours)
        await db.execute("INSERT INTO user_sessions (id, token_hash, user_id, workspace_id, expires_at) VALUES (?, ?, ?, ?, ?)", (session_id, _token_hash(token), user["id"], membership["workspace_id"], expires_at.isoformat()))
        await db.commit()
    return token, SessionPrincipal(str(user["id"]), str(membership["workspace_id"]), str(membership["role"]), session_id)


async def get_session_principal(token: str | None, *, now: dt.datetime | None = None) -> SessionPrincipal | None:
    if not token:
        return None
    now = now or _utcnow()
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT s.id session_id, s.user_id, s.workspace_id, s.expires_at, u.status user_status,
                      w.status workspace_status, m.status membership_status, m.role
               FROM user_sessions s JOIN users u ON u.id=s.user_id JOIN workspaces w ON w.id=s.workspace_id
               JOIN workspace_memberships m ON m.user_id=s.user_id AND m.workspace_id=s.workspace_id
               WHERE s.token_hash=? AND s.revoked_at IS NULL""", (_token_hash(token),)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or _parse_timestamp(row["expires_at"]) <= now:
            return None
        if row["user_status"] != "active" or row["workspace_status"] != "active" or row["membership_status"] != "active":
            return None
        await db.execute("UPDATE user_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?", (row["session_id"],))
        await db.commit()
    return SessionPrincipal(str(row["user_id"]), str(row["workspace_id"]), str(row["role"]), str(row["session_id"]))


async def revoke_session(session_id: str) -> None:
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE id=? AND revoked_at IS NULL", (session_id,))
        await db.commit()


async def change_password(principal: SessionPrincipal, current_password: str, new_password: str) -> None:
    replacement = hash_password(new_password)
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await _require_account_session(db, principal, password=current_password)
            await db.execute("UPDATE users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (replacement, principal.user_id))
            await db.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND id<>? AND revoked_at IS NULL", (principal.user_id, principal.session_id))
            await db.commit()
        except Exception:
            await db.rollback(); raise


async def create_password_reset(email: str, *, now=None) -> str | None:
    """Create a delivery token; callers must return a generic response publicly."""
    issued = now or _utcnow()
    token = secrets.token_urlsafe(32)
    async with aiosqlite.connect(database.DB_PATH) as db:
        user = await (await db.execute("SELECT id FROM users WHERE email=? AND status='active'", (email.strip().lower(),))).fetchone()
        if not user:
            return None
        await db.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL", (issued.isoformat(), user[0]))
        await db.execute(
            "INSERT INTO password_reset_tokens (id,user_id,token_hash,expires_at) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), user[0], _token_hash(token), (issued + dt.timedelta(minutes=30)).isoformat()),
        )
        await db.commit()
    return token


async def consume_password_reset(token: str, new_password: str, *, now=None) -> None:
    issued, replacement = now or _utcnow(), hash_password(new_password)
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            lock = " FOR UPDATE" if is_postgres() else ""
            row = await (await db.execute(
                "SELECT id,user_id,expires_at FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL" + lock,
                (_token_hash(token),),
            )).fetchone()
            if not row or _parse_timestamp(row[2]) <= issued:
                raise PermissionError("Reset token is invalid or expired.")
            changed = await db.execute("UPDATE password_reset_tokens SET used_at=? WHERE id=? AND used_at IS NULL", (issued.isoformat(), row[0]))
            if changed.rowcount != 1:
                raise PermissionError("Reset token is invalid or expired.")
            await db.execute("UPDATE users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (replacement, row[1]))
            await db.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND revoked_at IS NULL", (row[1],))
            await db.commit()
        except Exception:
            await db.rollback(); raise


async def create_email_verification(principal: SessionPrincipal, *, now=None) -> str:
    issued, token = now or _utcnow(), secrets.token_urlsafe(32)
    async with aiosqlite.connect(database.DB_PATH) as db:
        await _require_account_session(db, principal, now=issued)
        await db.execute("UPDATE email_verification_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL", (issued.isoformat(), principal.user_id))
        await db.execute(
            "INSERT INTO email_verification_tokens (id,user_id,token_hash,expires_at) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), principal.user_id, _token_hash(token), (issued + dt.timedelta(hours=24)).isoformat()),
        )
        await db.commit()
    return token


async def consume_email_verification(token: str, *, now=None) -> None:
    issued = now or _utcnow()
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            lock = " FOR UPDATE" if is_postgres() else ""
            row = await (await db.execute(
                "SELECT id,user_id,expires_at FROM email_verification_tokens WHERE token_hash=? AND used_at IS NULL" + lock,
                (_token_hash(token),),
            )).fetchone()
            if not row or _parse_timestamp(row[2]) <= issued:
                raise PermissionError("Verification token is invalid or expired.")
            await db.execute("UPDATE email_verification_tokens SET used_at=? WHERE id=?", (issued.isoformat(), row[0]))
            await db.execute("UPDATE users SET email_verified_at=COALESCE(email_verified_at,?), updated_at=CURRENT_TIMESTAMP WHERE id=?", (issued.isoformat(), row[1]))
            await db.commit()
        except Exception:
            await db.rollback(); raise


async def session_public_profile(principal: SessionPrincipal) -> dict[str, object]:
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""SELECT u.email, u.display_name, u.email_verified_at,
                                        CASE WHEN mf.user_id IS NULL THEN FALSE ELSE TRUE END AS mfa_enabled,
                                        w.name workspace_name, w.slug workspace_slug,
                                        COALESCE(e.plan_key, 'free') AS plan_key,
                                        COALESCE(e.billing_state, 'non_billed') AS billing_state,
                                        COALESCE(e.limits_json, '{}') AS limits_json
                                 FROM users u JOIN workspaces w ON w.id=?
                                 LEFT JOIN user_mfa_credentials mf ON mf.user_id=u.id
                                 LEFT JOIN workspace_entitlements e ON e.workspace_id=w.id
                                 WHERE u.id=?""", (principal.workspace_id, principal.user_id)) as cursor:
            row = await cursor.fetchone()
    if not row:
        raise PermissionError("Session account no longer exists")
    return {"user_id": principal.user_id, "email": str(row["email"]), "display_name": str(row["display_name"]), "workspace_id": principal.workspace_id, "workspace_name": str(row["workspace_name"]), "workspace_slug": str(row["workspace_slug"]), "role": principal.role, "email_verified": row["email_verified_at"] is not None, "mfa_enabled": bool(row["mfa_enabled"]), "plan_key": str(row["plan_key"]), "billing_state": str(row["billing_state"]), "limits_json": str(row["limits_json"])}


async def legacy_owner_principal() -> SessionPrincipal | None:
    """Temporary compatibility identity: exactly one active Owner membership."""
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""SELECT m.user_id, m.workspace_id, m.role FROM workspace_memberships m
                                 JOIN users u ON u.id=m.user_id JOIN workspaces w ON w.id=m.workspace_id
                                 WHERE m.status='active' AND m.role='owner' AND u.status='active' AND w.status='active'""") as cursor:
            rows = await cursor.fetchall()
    if len(rows) != 1:
        return None
    row = rows[0]
    return SessionPrincipal(str(row["user_id"]), str(row["workspace_id"]), str(row["role"]), None, legacy=True)
