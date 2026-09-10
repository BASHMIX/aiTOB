"""PostgreSQL-only storage acceptance tests.

Run explicitly with AITOB_PG_TEST_URL; ordinary isolated SQLite tests never
need a reachable PostgreSQL service.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

from backend.core import database
from backend.core.action_proposals import approve_action_proposal, create_action_proposal
from backend.core.storage import _query
from backend.core.workflow_outbox import ExternalEffectUnknown, WorkflowOutboxWorker


PG_TEST_URL = os.getenv("AITOB_PG_TEST_URL")
pytestmark = pytest.mark.skipif(not PG_TEST_URL, reason="requires explicit AITOB_PG_TEST_URL")


@pytest.fixture(autouse=True)
async def isolated_postgres(monkeypatch: pytest.MonkeyPatch):
    import psycopg
    from psycopg import sql
    parts = urlsplit(PG_TEST_URL or "")
    name = "aitob_test_" + uuid.uuid4().hex
    admin = urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment))
    target = urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    monkeypatch.setenv("DATABASE_URL", target)
    try:
        await database.init_db()
        yield
    finally:
        with psycopg.connect(admin, autocommit=True) as db:
            db.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_placeholders_preserve_sql_literals_and_comments():
    sql = "SELECT '?', \"?\", ? -- ? :ignored\n, :value /* ? :also_ignored */; SELECT $$? :inside$$, :outside"
    assert _query(sql) == "SELECT '?', \"?\", %s -- ? :ignored\n, %(value)s /* ? :also_ignored */; SELECT $$? :inside$$, %(outside)s"
    assert _query("SELECT ?::text, :value::integer") == "SELECT %s::text, %(value)s::integer"


def test_sqlite_compatibility_rewrites_are_limited_to_legacy_executable_forms():
    assert _query("INSERT OR IGNORE INTO player_overrides (id) VALUES (?)") == (
        "INSERT INTO player_overrides (id) VALUES (%s) ON CONFLICT DO NOTHING"
    )
    # Date arithmetic is repository-owned so a compatibility regex can never
    # rewrite a user-facing literal or SQL comment.
    assert _query("SELECT datetime('now', '-2 minutes'), '?' /* datetime('now') */") == (
        "SELECT datetime('now', '-2 minutes'), '?' /* datetime('now') */"
    )
    for statement in (
        "SELECT 'INSERT OR IGNORE INTO sample'",
        "SELECT 'INSERT OR REPLACE INTO connections (key, value) VALUES (?, ?)'",
        "SELECT 1 /* INSERT OR IGNORE INTO sample */",
    ):
        assert _query(statement) == statement


@pytest.mark.asyncio
async def test_parameterized_sql_preserves_percent_literals_and_modulo():
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        row = await (await db.execute("SELECT '100%' AS label, ? % 2 AS remainder", (3,))).fetchone()
        assert row["label"] == "100%"
        assert row["remainder"] == 1


@pytest.mark.asyncio
async def test_begin_immediate_compatibility_starts_transaction_without_global_lock():
    """Legacy syntax starts a transaction; repositories own scoped locking."""
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute("SELECT 1 AS active")).fetchone()
        assert row["active"] == 1
        await db.rollback()


def test_nested_comments_and_escape_strings_do_not_create_parameters():
    statement = r"SELECT E'escaped\' ? :hidden', ? /* outer /* inner */ ? :hidden */"
    assert _query(statement) == statement.replace(", ? /*", ", %s /*")


@pytest.mark.asyncio
async def test_concurrent_approval_locks_one_proposal_and_one_command():
    await database.upsert_tournament("pg/one", "PG", "Bracket", "event", "Game", "{}")
    await database.upsert_active_match("pg-set", **{
        "tournament_slug": "pg/one", "p1_name": "One", "p2_name": "Two",
        "p1_entrant_id": "1", "p2_entrant_id": "2", "status": "not_started",
    })
    proposal = await create_action_proposal(tournament_slug="pg/one", action_type="call", match_id="pg-set", reason="concurrency")
    first, second = await asyncio.gather(approve_action_proposal(proposal["id"]), approve_action_proposal(proposal["id"]))
    assert first["command_id"] == second["command_id"]
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        row = await (await db.execute("SELECT COUNT(*) FROM hub_commands WHERE source='proposal'")).fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_active_match_boolean_updates_bind_as_postgres_booleans():
    """Bot Call updates must not send SQLite 0/1 into PostgreSQL BOOLEAN columns."""
    await database.upsert_tournament("pg/bool", "PG", "Bracket", "event", "Game", "{}")
    await database.upsert_active_match(
        "pg-bool", tournament_slug="pg/bool", p1_name="One", p2_name="Two",
        p1_entrant_id="1", p2_entrant_id="2", status="not_started",
    )
    assert await database.update_active_match("pg-bool", auto_dq_disarmed=0)
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        row = await (await db.execute(
            "SELECT auto_dq_disarmed FROM active_matches WHERE set_id=?", ("pg-bool",)
        )).fetchone()
    assert row[0] is False


@pytest.mark.asyncio
async def test_concurrent_outbox_claim_dispatches_one_effect_and_retry_is_idempotent():
    """Two independent workers may observe work, but only one owns its lease."""
    await database.enqueue_workflow_outbox_v2({
        "event_id": "pg-effect", "match_id": "pg-match", "event_type": "discord_call",
        "deduplication_key": "pg-effect-key", "payload": {"safe": True},
    })
    delivered: list[str] = []

    async def dispatch(event: dict) -> None:
        delivered.append(event["event_id"])

    first = WorkflowOutboxWorker(dispatch, lease_owner="pg-worker-a")
    second = WorkflowOutboxWorker(dispatch, lease_owner="pg-worker-b")
    completed = await asyncio.gather(first.run_once(), second.run_once())
    assert sum(completed) == 1
    assert delivered == ["pg-effect"]

    # A later retry sees the durable completion and cannot redeliver it.
    assert await first.run_once() == 0
    assert delivered == ["pg-effect"]


@pytest.mark.asyncio
async def test_failed_transaction_rolls_back_before_independent_retry():
    await database.upsert_tournament("pg/rollback", "PG", "Bracket", "event", "Game", "{}")
    proposal = await create_action_proposal(
        tournament_slug="pg/rollback", action_type="announcement_draft",
        payload={"text": "safe"}, reason="rollback",
    )
    # Roll back an explicit, independent transaction after taking the row lock.
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("BEGIN")
        await db.execute("SELECT id FROM action_proposals WHERE id=? FOR UPDATE", (proposal["id"],))
        await db.execute("UPDATE action_proposals SET approval_status='rejected' WHERE id=?", (proposal["id"],))
        await db.rollback()

    approved = await approve_action_proposal(proposal["id"])
    assert approved["approval_status"] == "approved"
    assert approved["command_id"]


@pytest.mark.asyncio
async def test_postgres_schema_migration_is_tracked_and_reentrant():
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        before = (await (await db.execute("SELECT count(*) FROM schema_migration_history")).fetchone())[0]
    await asyncio.gather(database.init_db(), database.init_db())
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        after = (await (await db.execute("SELECT count(*) FROM schema_migration_history")).fetchone())[0]
    assert before == after and before > 0


@pytest.mark.asyncio
async def test_concurrent_station_reservations_lock_one_station_owner():
    await database.upsert_tournament("pg/stations", "PG", "Bracket", "event", "Game", "{}")
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("UPDATE tournaments SET provider_type='challonge' WHERE slug='pg/stations'")
        await db.commit()
    for match_id in ("pg-station-a", "pg-station-b"):
        await database.upsert_active_match(match_id, **{
            "tournament_slug": "pg/stations", "p1_name": "One", "p2_name": "Two",
            "p1_entrant_id": "1", "p2_entrant_id": "2", "status": "not_started",
        })

    async def reserve(match_id: str):
        return await database.apply_local_workflow_transition_v2(
            match_id, "not_started", "assign_station", fields={"station_id": "station_1"}, effects=[]
        )

    results = await asyncio.gather(reserve("pg-station-a"), reserve("pg-station-b"), return_exceptions=True)
    assert sum(not isinstance(result, Exception) for result in results) == 1, repr(results)
    assert sum(isinstance(result, ValueError) and "occupied" in str(result) for result in results) == 1
    station = await database.get_station("station_1")
    assert station["active_match_id"] in {"pg-station-a", "pg-station-b"}


@pytest.mark.asyncio
async def test_provider_ledger_idempotency_and_lease_claim_are_single_owner():
    command = {
        "id": "pg-provider-command", "tournament_slug": "pg/ledger", "set_id": "pg-set",
        "provider_type": "challonge", "provider_account_id": "pg-account", "action": "score",
        "idempotency_key": "pg-provider-key", "payload_digest": "digest",
    }
    first, second = await asyncio.gather(
        database.create_provider_command_v2(command),
        database.create_provider_command_v2({**command, "id": "pg-provider-command-retry"}),
    )
    assert first["id"] == second["id"]
    assert first["id"] in {"pg-provider-command", "pg-provider-command-retry"}
    now, lease = "2026-09-07T00:00:00+00:00", "2026-09-07T00:01:00+00:00"
    claimed_a, claimed_b = await asyncio.gather(
        database.claim_due_provider_commands_v2(now, lease, lease_owner="ledger-a"),
        database.claim_due_provider_commands_v2(now, lease, lease_owner="ledger-b"),
    )
    assert len(claimed_a) + len(claimed_b) == 1
    owner = (claimed_a or claimed_b)[0]["lease_owner"]
    assert owner in {"ledger-a", "ledger-b"}


@pytest.mark.asyncio
async def test_dispatcher_claim_and_kill_switch_are_postgres_atomic():
    await database.upsert_tournament("pg/dispatch", "PG", "Bracket", "event", "Game", "{}")
    await database.set_setting("auto_dispatch_master_switch", "on")
    first, second = await asyncio.gather(
        database.claim_dispatcher_match("pg-dispatch-set", "pg/dispatch"),
        database.claim_dispatcher_match("pg-dispatch-set", "pg/dispatch"),
    )
    assert [first, second].count(True) == 1
    await database.add_hub_command("call_match pg-dispatch-set", source="dispatcher")
    await database.add_hub_command("call_match manual", source="manual")
    assert await database.cancel_pending_dispatcher_work("pg/dispatch") == 2
    pending = await database.get_pending_hub_commands()
    assert [row["command_text"] for row in pending] == ["call_match manual"]


@pytest.mark.asyncio
async def test_unknown_external_outbox_outcome_requires_review_not_blind_retry():
    await database.enqueue_workflow_outbox_v2({
        "event_id": "pg-unknown-effect", "match_id": "pg-match", "event_type": "discord_call",
        "deduplication_key": "pg-unknown-effect-key", "payload": {},
    })

    async def uncertain_dispatch(_: dict) -> None:
        raise ExternalEffectUnknown("receiver outcome was not acknowledged")

    worker = WorkflowOutboxWorker(uncertain_dispatch, lease_owner="unknown-effect-worker")
    assert await worker.run_once() == 0
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        row = await (await db.execute(
            "SELECT status FROM workflow_outbox WHERE event_id=?", ("pg-unknown-effect",)
        )).fetchone()
    assert row["status"] == "needs_review"
    assert await worker.run_once() == 0


@pytest.mark.asyncio
async def test_concurrent_owner_bootstrap_creates_one_workspace(monkeypatch):
    from backend.core.workspace_auth import bootstrap_initial_owner_from_env
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_EMAIL", "bootstrap@example.test")
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", "temporary-test-password")
    outcomes = await asyncio.gather(
        bootstrap_initial_owner_from_env(), bootstrap_initial_owner_from_env(),
        return_exceptions=True,
    )
    assert sorted(outcomes) == [False, True]
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        assert (await (await db.execute("SELECT count(*) FROM workspaces")).fetchone())[0] == 1


@pytest.mark.asyncio
async def test_ai_usage_reservations_obey_limit_across_connections():
    from backend.core.ai_service import _reserve, update_ai_config, AIUsageLimitError
    config = await update_ai_config({"request_limit": 1, "token_limit": 100_000})
    outcomes = await asyncio.gather(*(_reserve(config, "ai/test", 10) for _ in range(8)), return_exceptions=True)
    assert sum(isinstance(value, str) for value in outcomes) == 1
    assert sum(isinstance(value, AIUsageLimitError) for value in outcomes) == 7


@pytest.mark.asyncio
async def test_auth_rate_limit_concurrent_first_window_is_not_reset_by_upsert_race():
    """A missing limiter row must not let concurrent first requests all pass.

    This specifically exercises the race where two PostgreSQL connections see
    no row, then both attempt an INSERT.  The conflict path must increment the
    already-created window rather than reset it to one.
    """
    from backend.core.workspace_auth import enforce_auth_rate_limit

    outcomes = await asyncio.gather(*(
        enforce_auth_rate_limit("test", "same-subject", limit=1, window_seconds=3600)
        for _ in range(8)
    ), return_exceptions=True)
    assert sum(value is None for value in outcomes) == 1
    assert sum(isinstance(value, PermissionError) for value in outcomes) == 7


@pytest.mark.asyncio
async def test_authenticated_api_limiter_is_shared_across_process_like_requests(monkeypatch):
    """The API dependency charges one DB-backed window, not one process-local counter."""
    from types import SimpleNamespace
    from backend.core.workspace_auth import SessionPrincipal, enforce_authenticated_api_rate_limit

    monkeypatch.setenv("AITOB_API_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("AITOB_API_RATE_LIMIT_WINDOW_SECONDS", "3600")
    principal = SessionPrincipal("user-a", "workspace-a", "owner", "session-a")

    def request():
        return SimpleNamespace(
            url=SimpleNamespace(path="/api/matches"), method="POST",
            client=SimpleNamespace(host="independent-process"), state=SimpleNamespace(),
        )

    outcomes = await asyncio.gather(*(
        enforce_authenticated_api_rate_limit(request(), principal) for _ in range(2)
    ), return_exceptions=True)
    assert sum(value is None for value in outcomes) == 1
    assert sum(isinstance(value, PermissionError) for value in outcomes) == 1


@pytest.mark.asyncio
async def test_retention_is_atomic_when_two_workers_run_together():
    """Concurrent housekeeping cannot double-delete or touch workspace data."""
    import datetime as dt
    import uuid
    from backend.core.retention import purge_expired_auth_artifacts

    user_id = str(uuid.uuid4())
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)).isoformat()
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (id,email,display_name,password_hash) VALUES (?,?,?,?)",
            (user_id, f"retention-pg-{user_id}@example.test", "Retention PG", "hash"),
        )
        await db.execute(
            "INSERT INTO password_reset_tokens (id,user_id,token_hash,expires_at,used_at) VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), user_id, f"old-{user_id}", old, old),
        )
        await db.commit()

    counts = await asyncio.gather(
        purge_expired_auth_artifacts(retention_days=30),
        purge_expired_auth_artifacts(retention_days=30),
    )
    assert sum(item["password_reset_tokens"] for item in counts) == 1
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        remaining = await (await db.execute(
            "SELECT COUNT(*) FROM password_reset_tokens WHERE user_id=?", (user_id,)
        )).fetchone()
    assert remaining[0] == 0


@pytest.mark.asyncio
async def test_recovery_code_is_consumed_once_across_postgres_sessions(monkeypatch):
    from cryptography.fernet import Fernet
    from backend.core.workspace_auth import (
        bootstrap_initial_owner_from_env, authenticate_password,
        begin_totp_setup, enable_totp, _totp_at, _totp_counter,
    )
    monkeypatch.setenv("AITOB_AUTH_MASTER_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_EMAIL", "mfa@example.test")
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", "temporary-test-password")
    await bootstrap_initial_owner_from_env()
    _, principal = await authenticate_password("mfa@example.test", "temporary-test-password")
    secret = await begin_totp_setup(principal, "temporary-test-password")
    codes = await enable_totp(principal, secret, _totp_at(secret, _totp_counter()))
    outcomes = await asyncio.gather(*(
        authenticate_password("mfa@example.test", "temporary-test-password", totp_code=codes[0])
        for _ in range(4)
    ), return_exceptions=True)
    assert sum(isinstance(value, tuple) for value in outcomes) == 1
    assert sum(isinstance(value, PermissionError) for value in outcomes) == 3


@pytest.mark.asyncio
async def test_restart_after_external_effect_does_not_redeliver(monkeypatch):
    await database.enqueue_workflow_outbox_v2({
        "event_id": "crash-effect", "match_id": "match", "event_type": "discord_call",
        "deduplication_key": "crash-effect", "payload": {},
    })
    delivered = []
    async def dispatch(event):
        delivered.append(event["event_id"])
    async def process_crash(*args, **kwargs):
        raise asyncio.CancelledError()
    with monkeypatch.context() as patch:
        patch.setattr(database, "mark_workflow_outbox_completed_v2", process_crash)
        with pytest.raises(asyncio.CancelledError):
            await WorkflowOutboxWorker(dispatch, lease_owner="before").run_once(now="2099-01-01T00:00:00+00:00")
    assert await WorkflowOutboxWorker(dispatch, lease_owner="after").run_once(now="2099-01-01T00:02:00+00:00") == 0
    assert delivered == ["crash-effect"]
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        assert (await (await db.execute("SELECT status FROM workflow_outbox WHERE event_id='crash-effect'")).fetchone())[0] == "needs_review"


@pytest.mark.asyncio
async def test_concurrent_invite_acceptance_and_last_owner_removal(monkeypatch):
    from backend.core.workspace_auth import (
        bootstrap_initial_owner_from_env, authenticate_password,
        create_workspace_invitation, accept_workspace_invitation,
        disable_workspace_member, set_workspace_member_role, SessionPrincipal,
    )
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_EMAIL", "owner@example.test")
    monkeypatch.setenv("AITOB_BOOTSTRAP_OWNER_PASSWORD", "temporary-test-password")
    await bootstrap_initial_owner_from_env()
    _, owner = await authenticate_password("owner@example.test", "temporary-test-password")
    _, token = await create_workspace_invitation(owner, "second@example.test", "viewer")
    accepted = await asyncio.gather(
        accept_workspace_invitation(token, "temporary-test-password", "Second"),
        accept_workspace_invitation(token, "temporary-test-password", "Second"),
        return_exceptions=True,
    )
    assert sum(isinstance(value, PermissionError) for value in accepted) == 1
    second = next(value for value in accepted if not isinstance(value, Exception))
    await set_workspace_member_role(owner, second.user_id, "owner")
    second = SessionPrincipal(second.user_id, second.workspace_id, "owner", None)
    outcomes = await asyncio.gather(
        disable_workspace_member(owner, owner.user_id),
        disable_workspace_member(second, second.user_id), return_exceptions=True,
    )
    assert outcomes.count(None) == 1
    assert sum(isinstance(value, ValueError) for value in outcomes) == 1
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        assert (await (await db.execute("SELECT count(*) FROM workspace_memberships WHERE role='owner' AND status='active'")).fetchone())[0] == 1
