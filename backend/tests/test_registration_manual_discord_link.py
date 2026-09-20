import pytest

from backend.core import database
from backend.core.player_registration import RegistrationError, link_discord_member, unlink_discord_member, upsert_enrollment
from backend.core.storage import dbapi as aiosqlite


@pytest.fixture
async def link_db(tmp_path, monkeypatch):
    db_path = tmp_path / "registration-link.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    await database.init_db()
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES ('w1', 'w1', 'Workspace')")
        await db.execute("INSERT INTO tournaments (slug, name, workspace_id) VALUES ('t1', 'Tournament', 'w1')")
        await db.commit()
    return database.DB_PATH


@pytest.mark.asyncio
async def test_manual_link_validates_snowflake_and_enforces_one_to_one(link_db):
    first = await upsert_enrollment("t1", "w1", provider_entrant_id="e1", gamertag="Alpha")
    second = await upsert_enrollment("t1", "w1", provider_entrant_id="e2", gamertag="Bravo")
    linked = await link_discord_member(first["id"], "t1", "w1", "303608372999000111", actor_id="organizer", guild_id="guild-1")
    assert linked["discord_link_state"] == "linked"
    with pytest.raises(RegistrationError, match="discord_user_already_linked"):
        await link_discord_member(second["id"], "t1", "w1", "303608372999000111", actor_id="organizer", guild_id="guild-1")
    with pytest.raises(RegistrationError, match="invalid_discord_user"):
        await link_discord_member(second["id"], "t1", "w1", "not-a-snowflake", actor_id="organizer")
    removed = await unlink_discord_member(first["id"], "t1", "w1", actor_id="organizer")
    assert removed["discord_link_state"] == "unlinked"
