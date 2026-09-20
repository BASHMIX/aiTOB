from datetime import UTC, datetime

import pytest

from backend.core import database
from backend.core.player_registration import (
    get_registration_config,
    registration_window_state,
    set_registration_status,
    upsert_registration_config,
)
from backend.core.storage import dbapi


@pytest.fixture
async def window_db(tmp_path, monkeypatch):
    database_dsn = tmp_path / "registration-window.pg"
    monkeypatch.setattr(database, "DATABASE_DSN", str(database_dsn))
    await database.init_db()
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES ('w1', 'w1', 'Workspace')")
        await db.execute("INSERT INTO users (id, email, display_name, password_hash) VALUES ('u1', 'owner@example.test', 'Owner', 'hash')")
        await db.execute("INSERT INTO tournaments (slug, name, workspace_id, provider_type) VALUES ('t1', 'Tournament', 'w1', 'startgg')")
        await db.commit()
    return database.DATABASE_DSN


@pytest.mark.asyncio
async def test_window_uses_server_time_and_schedule_versions(window_db):
    config = await upsert_registration_config(
        "t1", "w1", "u1", {
            "enabled": True, "destination_external_id": "registration",
            "opens_at": "2026-09-13T10:00:00+00:00", "closes_at": "2026-09-13T12:00:00+00:00",
        },
    )
    assert config["schedule_version"] == 1
    moment = datetime(2026, 9, 13, 11, 0, tzinfo=UTC)
    assert registration_window_state(config, now=moment) == "open"
    assert registration_window_state(config, now=moment.replace(hour=9)) == "scheduled"
    assert registration_window_state(config, now=moment.replace(hour=12)) == "closed"
    opened = await set_registration_status("t1", "w1", "open", actor_id="u1")
    assert opened["status"] == "open"
    assert opened["schedule_version"] == 2
    assert (await get_registration_config("t1", "w1"))["schedule_version"] == 2
