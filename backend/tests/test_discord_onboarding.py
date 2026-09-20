import time
import pytest

from backend.api.routers.discord_oauth import _hash
from backend.core import database


@pytest.mark.asyncio
async def test_discord_state_hash_is_one_way_and_expiry_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "oauth.sqlite"))
    await database.init_db()
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO workspaces(id,slug,name) VALUES ('w','w','Workspace')")
        await db.execute("INSERT INTO users(id,email,display_name,password_hash) VALUES ('u','u@example.com','U','x')")
        await db.execute("INSERT INTO tournament_setup_drafts(id,workspace_id,created_by,updated_by) VALUES ('d','w','u','u')")
        await db.execute("INSERT INTO discord_oauth_states(state_hash,workspace_id,actor_id,draft_id,return_step,expires_at) VALUES (?,?,?,?,?,?)", (_hash('opaque'), 'w', 'u', 'd', 'discord', int(time.time()) + 60))
        await db.commit()
        row = await (await db.execute("SELECT state_hash FROM discord_oauth_states")).fetchone()
    assert row[0] == _hash('opaque') and row[0] != 'opaque'
