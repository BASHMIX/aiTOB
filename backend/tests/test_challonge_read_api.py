from __future__ import annotations

import json

import pytest

from backend.api.routers import tournaments
from backend.core import database
from backend.core.contracts import ProviderEntrant, ProviderSet, ProviderSetState


@pytest.fixture
async def read_api_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "read-api.pg"))
    await database.init_db()
    slug = "challonge:account:fnc-jo:1"
    await database.upsert_tournament(slug, "FNC", None, None, None, json.dumps({}), provider_type="challonge", provider_tournament_id="1", provider_subdomain="fnc-jo", provider_account_id="account")
    match = ProviderSet(id="challonge:fnc-jo:1:m1", provider_set_id="m1", state=ProviderSetState.NOT_STARTED, provider_state_raw="open", entrant1=ProviderEntrant("p1", "Alpha"), entrant2=ProviderEntrant("p2", "Bravo"))
    await database.apply_challonge_snapshot(slug, "account", [match], [], scope="full_snapshot", revision="1", observed_at=None, covered_scopes={"full_snapshot"}, complete_pages=True)
    return slug


@pytest.mark.asyncio
async def test_ten_dashboard_set_reads_are_postgres_only_when_fresh(read_api_db, monkeypatch):
    calls = 0

    async def no_background(_slug):
        nonlocal calls
        calls += 1
        return False

    monkeypatch.setattr(tournaments.sync_manager, "maybe_sync_on_stale_open", no_background)
    snapshots = [await tournaments.api_get_sets(read_api_db) for _ in range(10)]

    assert calls == 10  # local freshness policy check only; no provider operation.
    assert all(item["sets"][0]["p1"] == "Alpha" for item in snapshots)
    assert all(item["stale_refresh_scheduled"] is False for item in snapshots)
    assert snapshots[-1]["last_provider_sync"] is not None
