"""Hub feed rows are isolated by durable workspace ownership."""

from __future__ import annotations

import pytest
from backend.core import database


@pytest.fixture
async def feed_test_db(tmp_path, monkeypatch):
    path = tmp_path / "feed.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    yield path

from backend.core.database import add_bot_feed, clear_bot_feed, get_bot_feed, init_db


@pytest.mark.asyncio
async def test_feed_reads_are_workspace_scoped(feed_test_db):
    await init_db()
    await add_bot_feed("workspace-a", workspace_id="ws-a")
    await add_bot_feed("workspace-b", workspace_id="ws-b")
    assert [row["message"] for row in await get_bot_feed(workspace_id="ws-a")] == ["workspace-a"]
    assert [row["message"] for row in await get_bot_feed(workspace_id="ws-b")] == ["workspace-b"]


@pytest.mark.asyncio
async def test_feed_clear_does_not_remove_another_workspace(feed_test_db):
    await init_db()
    await add_bot_feed("workspace-a", workspace_id="ws-a")
    await add_bot_feed("workspace-b", workspace_id="ws-b")
    await clear_bot_feed("ws-a")
    assert await get_bot_feed(workspace_id="ws-a") == []
    assert [row["message"] for row in await get_bot_feed(workspace_id="ws-b")] == ["workspace-b"]
