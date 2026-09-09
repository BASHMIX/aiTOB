"""Phase-10 acceptance checks for SQLite-only organizer freshness diagnostics."""
from __future__ import annotations

import json

import pytest

from backend.core import database


@pytest.fixture
async def freshness_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "freshness.sqlite"))
    await database.init_db()
    await database.upsert_tournament(
        "challonge:freshness", "Freshness", None, None, None, json.dumps({}),
        provider_type="challonge", provider_tournament_id="99",
    )
    await database.set_tournament_sync_status("challonge:freshness", True)
    return "challonge:freshness"


@pytest.mark.asyncio
async def test_sets_response_exposes_freshness_and_uses_one_stale_open_admission(freshness_db, monkeypatch):
    from backend.api.routers import tournaments

    calls: list[str] = []

    async def stale_open(slug: str) -> bool:
        calls.append(slug)
        return False

    monkeypatch.setattr(tournaments.sync_manager, "maybe_sync_on_stale_open", stale_open)
    response = await tournaments.api_get_sets(freshness_db)

    assert response["last_provider_sync"] is not None
    assert response["sync_status"] == "ready"
    assert response["stale_refresh_scheduled"] is False
    assert response["economy_sync_on_stale_open"] is True
    assert calls == [freshness_db]


@pytest.mark.asyncio
async def test_sync_status_is_sqlite_only_and_explains_economy_discovery(freshness_db, monkeypatch):
    from backend.api.routers import tournaments

    async def state(_slug: str):
        return {"mode": "economy", "active_match": False}

    monkeypatch.setattr(tournaments, "get_live_sync_state_v2", state)
    response = await tournaments.api_tournament_sync_status(freshness_db)

    assert response["last_provider_sync"] is not None
    assert response["sync_status"] == "ready"
    assert response["mode"] == "economy"
    assert response["economy_message"] == "Remote changes appear on Sync now or a stale-open refresh."
