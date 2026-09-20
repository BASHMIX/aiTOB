from cryptography.fernet import Fernet
import pytest

from backend.core import database
from backend.core.ai_service import (
    get_workspace_ai_config, set_workspace_ai_key, update_workspace_ai_config,
)


@pytest.mark.asyncio
async def test_workspace_ai_keys_are_separate_and_write_only(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workspace-ai.sqlite"))
    monkeypatch.setenv("AITOB_INTEGRATION_MASTER_KEY", Fernet.generate_key().decode("ascii"))
    await database.init_db()
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES ('w-a', 'workspace-a', 'A')")
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES ('w-b', 'workspace-b', 'B')")
        await db.commit()

    await set_workspace_ai_key("w-a", "gemini", "key-a")
    await set_workspace_ai_key("w-b", "openai", "key-b")
    await update_workspace_ai_config("w-a", {"mode": "read_only"})
    a = await get_workspace_ai_config("w-a")
    b = await get_workspace_ai_config("w-b")
    assert a["connections"]["gemini"]["configured"] is True
    assert b["connections"]["openai"]["configured"] is True
    assert a["connections"]["openai"]["configured"] is False
    assert "key-a" not in repr(a) and "key-b" not in repr(b)
