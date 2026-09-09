"""Workspace boundaries used by non-HTTP bot workers."""

from __future__ import annotations

import pytest

from backend.core import database


@pytest.fixture
async def scoped_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "worker-scope.sqlite"))
    await database.init_db()
    await database.upsert_tournament("same/a", "A", "", "", "", "{}", workspace_id="ws-a")
    await database.upsert_tournament("same/b", "B", "", "", "", "{}", workspace_id="ws-b")
    yield


@pytest.mark.asyncio
async def test_worker_tournament_enumeration_is_workspace_scoped(scoped_db):
    assert await database.get_all_tournament_slugs("ws-a") == ["same/a"]
    assert await database.get_all_tournament_slugs("ws-b") == ["same/b"]


@pytest.mark.asyncio
async def test_cfn_sync_does_not_update_the_other_workspace(scoped_db):
    await database.create_or_update_player("discord-a", workspace_id="ws-a", cfn_id="CFN-A")
    await database.create_or_update_player("discord-b", workspace_id="ws-b", cfn_id="CFN-B")
    for slug, workspace, set_id, discord in (
        ("same/a", "ws-a", "set-a", "discord-a"),
        ("same/b", "ws-b", "set-b", "discord-a"),
    ):
        await database.upsert_active_match(
            set_id, workspace_id=workspace, tournament_slug=slug,
            p1_discord=discord, p1_cfn=None, p1_name="P1", p2_name="P2",
        )

    await database.sync_player_cfns_to_matches("discord-a", "ws-a")
    own = await database.get_active_match("set-a", "ws-a")
    other = await database.get_active_match("set-b", "ws-b")
    assert own["p1_cfn"] == "CFN-A"
    assert other["p1_cfn"] is None

