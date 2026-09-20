import pytest
from backend.core import database
from backend.core.tournament_setup import create_draft, patch_draft
from backend.core.tournament_activation import materialize_draft, activate_tournament


@pytest.mark.asyncio
async def test_materialize_and_activate_are_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "activation.pg"))
    await database.init_db()
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces(id,slug,name) VALUES ('w','w','W')")
        await db.execute("INSERT INTO users(id,email,display_name,password_hash) VALUES ('u','u@example.com','U','x')")
        await db.commit()
    draft = await create_draft("w", "u")
    draft = await patch_draft(draft["id"], "w", "u", section="provider_scope", value={"provider": "startgg", "account_id": "a", "selected_scope": {"external_id": "e", "name": "E"}, "tournament": {"external_id": "t", "canonical_slug": "t", "name": "T"}}, expected_revision=draft["revision"], current_step="provider")
    draft = await patch_draft(draft["id"], "w", "u", section="tournament_review", value={"display_name": "T"}, expected_revision=draft["revision"], current_step="tournament")
    materialized = await materialize_draft(draft["id"], "w", "u", expected_revision=draft["revision"])
    active = await activate_tournament("w", materialized["tournament_id"], "u", idempotency_key="x")
    replay = await activate_tournament("w", materialized["tournament_id"], "u", idempotency_key="x")
    assert active["status"] == replay["status"] == "active"
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        count = await (await db.execute("SELECT COUNT(*) FROM workflow_outbox WHERE event_type='initial_sync'")).fetchone()
    assert count[0] == 1
