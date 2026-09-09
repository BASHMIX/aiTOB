"""Regression coverage for tenant-scoped active-match writes.

The legacy ``set_id`` is still the physical primary key while the incremental
workspace migration is in progress.  A trusted workspace supplied by a caller
must nevertheless be part of every update predicate: a caller from another
workspace may not mutate a row merely by knowing its provider set id.
"""
from __future__ import annotations

import pytest

from backend.core import database


@pytest.mark.asyncio
async def test_workspace_scoped_active_match_update_rejects_foreign_match(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "active-match-scope.sqlite"))
    await database.init_db()
    await database.upsert_active_match(
        "provider-set-101",
        workspace_id="workspace-owner",
        tournament_slug="owner-tournament",
        p1_name="Owner Player",
        status="not_started",
    )

    changed = await database.update_active_match(
        "provider-set-101",
        workspace_id="workspace-other",
        p1_name="Cross-tenant write",
    )

    assert changed is False
    owner = await database.get_active_match("provider-set-101", "workspace-owner")
    assert owner is not None
    assert owner["p1_name"] == "Owner Player"
    assert await database.get_active_match("provider-set-101", "workspace-other") is None


@pytest.mark.asyncio
async def test_station_helpers_do_not_treat_another_workspace_match_as_local_usage(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "active-match-station-scope.sqlite"))
    await database.init_db()
    await database.upsert_active_match(
        "provider-set-202",
        workspace_id="workspace-owner",
        tournament_slug="owner-tournament",
        station_id="station-owner",
        status="called",
    )

    assert await database.assign_station_to_active_match(
        "provider-set-202", "station-other", workspace_id="workspace-other",
    ) is False
    assert await database.get_used_station_ids(
        "candidate-set", workspace_id="workspace-other",
    ) == set()
    assert await database.get_used_station_ids(
        "candidate-set", workspace_id="workspace-owner",
    ) == {"station-owner"}

    owner = await database.get_active_match("provider-set-202", "workspace-owner")
    assert owner is not None
    assert owner["station_id"] == "station-owner"
