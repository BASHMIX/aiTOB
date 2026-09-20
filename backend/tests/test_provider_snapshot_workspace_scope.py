"""Provider bracket snapshots cannot cross workspace boundaries."""
from __future__ import annotations

import pytest

from backend.core import database


@pytest.mark.asyncio
async def test_bracket_snapshot_read_and_sync_status_are_workspace_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "snapshot-scope.pg"))
    await database.init_db()
    await database.upsert_tournament(
        "same-slug", "Tenant A", None, None, None, "{}", workspace_id="ws-a",
    )
    await database.upsert_tournament(
        "same-slug-b", "Tenant B", None, None, None, "{}", workspace_id="ws-b",
    )
    await database.save_bracket_snapshot("same-slug", [{"id": "a-match"}], "ws-a")
    await database.set_tournament_sync_status("same-slug", True, workspace_id="ws-a")

    assert (await database.get_bracket_snapshot("same-slug", "ws-a"))["sets"] == [{"id": "a-match"}]
    assert await database.get_bracket_snapshot("same-slug", "ws-b") == {"sets": [], "synced_at": None}
    owner = await database.get_tournament("same-slug", "ws-a")
    foreign = await database.get_tournament("same-slug", "ws-b")
    assert owner["provider_sync_status"] == "ready"
    assert foreign is None


@pytest.mark.asyncio
async def test_snapshot_write_rejects_wrong_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "snapshot-write-scope.pg"))
    await database.init_db()
    await database.upsert_tournament(
        "owned", "Tenant A", None, None, None, "{}", workspace_id="ws-a",
    )
    with pytest.raises(ValueError, match="not owned"):
        await database.save_bracket_snapshot("owned", [], "ws-b")
