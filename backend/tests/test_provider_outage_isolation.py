"""Phase 8: provider outage cannot stop Hub-local or other-provider work."""
from __future__ import annotations

import json
import pytest

from backend.core import database
from backend.core.contracts import ProviderSnapshotRequestV2, ProviderSnapshotV2, SnapshotScope
from backend.core.sync_coordinator import ProviderBackoffActive, SyncCoordinator


@pytest.mark.asyncio
async def test_challonge_429_backoff_does_not_block_startgg_snapshot():
    coordinator = SyncCoordinator(clock=lambda: 10.0)
    coordinator.set_backoff("challonge", "account", 99.0)
    blocked = ProviderSnapshotRequestV2("challonge", "account", "1", SnapshotScope.ACTIVE_MATCHES)
    allowed = ProviderSnapshotRequestV2("startgg", "account", "event", SnapshotScope.ACTIVE_MATCHES)
    with pytest.raises(ProviderBackoffActive):
        await coordinator.run_snapshot(blocked, lambda: _snapshot(blocked))
    result = await coordinator.run_snapshot(allowed, lambda: _snapshot(allowed))
    assert result.request.provider_type == "startgg"


@pytest.mark.asyncio
async def test_challonge_outage_does_not_block_local_call(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "outage.sqlite"))
    await database.init_db()
    slug = "challonge:account:outage:1"
    await database.upsert_tournament(slug, "Outage", None, None, None, json.dumps({}), provider_type="challonge", provider_tournament_id="1", provider_account_id="account")
    await database.upsert_active_match("challonge:outage", tournament_slug=slug, p1_name="A", p2_name="B", p1_entrant_id="p1", p2_entrant_id="p2", status="not_started", hub_status="available")
    from backend.core.match_commands import MatchCommandService
    service = MatchCommandService(feature_flags={"CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true"})
    async def offline(*_args):
        raise AssertionError("Local Call must not resolve Challonge while it is offline")
    monkeypatch.setattr(service, "_provider_for_match", offline)
    await service.call("challonge:outage")
    assert (await database.get_active_match("challonge:outage"))["hub_status"] == "called"


@pytest.mark.asyncio
async def test_token_expiry_keeps_score_as_local_draft_without_remote_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "expiry.sqlite"))
    await database.init_db()
    slug = "challonge:account:expiry:1"
    await database.upsert_tournament(slug, "Expiry", None, None, None, json.dumps({}), provider_type="challonge", provider_tournament_id="1", provider_account_id="account")
    await database.upsert_active_match("challonge:expiry", tournament_slug=slug, p1_name="A", p2_name="B", p1_entrant_id="p1", p2_entrant_id="p2", status="in_progress", hub_status="in_progress", p1_score=2, p2_score=0)
    from backend.core.match_commands import MatchCommandError, MatchCommandService
    from backend.core.providers.challonge.client import ChallongeError
    class ExpiredProvider:
        mutations = 0
        async def fetch_snapshot_v2(self, _request):
            raise ChallongeError("Challonge authorization failed or this tournament is inaccessible.")
        async def report_score(self, *_args):
            self.mutations += 1
    provider = ExpiredProvider()
    service = MatchCommandService(feature_flags={"CHALLONGE_LOCAL_WORKFLOW_ENABLED": "true", "CHALLONGE_SCORE_COMMANDS_ENABLED": "true"})
    monkeypatch.setattr(service, "_provider_for_match", lambda _match: _resolved(provider))
    with pytest.raises(MatchCommandError, match="local draft"):
        await service.submit_score("challonge:expiry", p1_score=2, p2_score=0)
    assert provider.mutations == 0
    assert (await database.get_active_match("challonge:expiry"))["sync_status"] == "failed"


async def _snapshot(request):
    return ProviderSnapshotV2(request=request, payload={})


async def _resolved(value):
    return value
