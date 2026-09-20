"""Start.gg parity lock before its dark V2 read adapter is introduced.

These assertions deliberately inspect the exact existing GraphQL documents and
variables, not just mapped results.  They are a regression contract for the
legacy provider and client behavior that V2 must wrap rather than rewrite.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from backend.core.contracts import ProviderSetState
from backend.core.contracts import (
    ProviderActionKind, ProviderCommandState, ProviderCommandV2,
    ProviderSnapshotRequestV2, SnapshotScope,
)
from backend.core.providers.startgg import queries
from backend.core.providers.startgg.client import StartGGClient
from backend.core.providers.startgg.provider import StartGGProvider


def _operation_name(document: str) -> str:
    return next(line.strip() for line in document.splitlines() if line.strip().startswith(("query ", "mutation ")))


@pytest.mark.asyncio
async def test_fetch_parity_preserves_operation_variables_request_count_and_order():
    calls: list[tuple[str, dict]] = []
    client = AsyncMock()

    async def query(document: str, variables: dict):
        calls.append((document, variables))
        if document == queries.TOURNAMENT_INFO:
            return {"tournament": {"id": "1", "name": "Fixture", "events": [], "streams": []}}
        if document == queries.TOURNAMENT_STATE:
            return {"tournament": {"events": [{"id": "event-1", "state": "ACTIVE", "phases": [{"id": "phase-1", "state": "ACTIVE"}]}]}}
        if document == queries.TOURNAMENT_SETS:
            return {"tournament": {"events": [{"id": "event-1", "name": "Fixture event", "sets": {"nodes": []}}]}}
        raise AssertionError("unexpected operation")

    client.query.side_effect = query
    provider = StartGGProvider(client=client)

    tournament = await provider.fetch_tournament("fixture")
    sets = await provider.fetch_sets("fixture")

    assert tournament and tournament.id == "1"
    assert sets == []
    assert [_operation_name(document) for document, _ in calls] == [
        "query TournamentInfo($slug: String!) {",
        "query TournamentState($slug: String!) {",
        "query TournamentSets($slug: String!, $page: Int!, $perPage: Int!, $phaseIds: [ID!]) {",
    ]
    assert [variables for _, variables in calls] == [
        {"slug": "fixture"},
        {"slug": "fixture"},
        {"slug": "fixture", "page": 1, "perPage": 250, "phaseIds": ["phase-1"]},
    ]


@pytest.mark.asyncio
async def test_fetch_event_game_metadata_uses_provider_catalog():
    client = AsyncMock()
    client.query.return_value = {
        "event": {
            "id": "event-1",
            "name": "SF6 Singles",
            "videogame": {
                "id": "43868",
                "name": "Street Fighter 6",
                "displayName": "SF6",
                "characters": [{"id": "1", "name": "Ryu"}, {"id": "2", "name": "Akuma"}],
                "stages": [{"id": "10", "name": "Training Room"}],
            },
        }
    }
    provider = StartGGProvider(client=client)

    result = await provider.fetch_event_game_metadata("event-1")

    assert result["videogame_id"] == "43868"
    assert result["characters"] == [{"id": "1", "name": "Ryu"}, {"id": "2", "name": "Akuma"}]
    assert result["stages"] == [{"id": "10", "name": "Training Room"}]
    client.query.assert_awaited_once_with(queries.EVENT_GAME_METADATA, {"eventId": "event-1"})


@pytest.mark.asyncio
async def test_mutation_parity_preserves_call_active_dq_reset_and_stream_queue_documents():
    client = StartGGClient(token="fixture")
    calls: list[tuple[str, dict]] = []

    async def query(document: str, variables: dict):
        calls.append((document, variables))
        if document == queries.SET_STATE:
            return {"set": {"state": 1}}
        if document == queries.SET_ENTRANT_ORDER:
            return {"set": {"slots": [{"entrant": {"id": "entrant-1"}}, {"entrant": {"id": "entrant-2"}}]}}
        return {"set": {"id": variables.get("setId")}}

    client.query = query  # type: ignore[method-assign]

    assert await client.mark_called("set-1") is True
    assert await client.mark_in_progress("set-1") is True
    assert await client.mark_set_dq("set-1", "entrant-1") is True
    assert await client.reset_set("set-1") is True
    assert await client.assign_stream("set-1", "stream-1") is True
    assert await client.remove_stream("set-1") is True

    assert "isDQ: true" in queries.MARK_SET_DQ
    assert [_operation_name(document) for document, _ in calls] == [
        "mutation MarkSetCalled($setId: ID!) {",
        "mutation MarkInProgress($setId: ID!) {",
        "query SetState($id: ID!) {",
        "mutation MarkInProgress($setId: ID!) {",
        "mutation MarkSetDQ($setId: ID!, $winnerId: ID!) {",
        "mutation ResetSet($setId: ID!) {",
        "mutation AssignStream($setId: ID!, $streamId: ID!) {",
    ]
    assert [variables for _, variables in calls] == [
        {"setId": "set-1"}, {"setId": "set-1"}, {"id": "set-1"},
        {"setId": "set-1"}, {"setId": "set-1", "winnerId": "entrant-1"},
        {"setId": "set-1"}, {"setId": "set-1", "streamId": "stream-1"},
    ]


@pytest.mark.asyncio
async def test_score_parity_preserves_preflight_order_game_data_and_provider_result():
    client = StartGGClient(token="fixture")
    calls: list[tuple[str, dict]] = []

    async def query(document: str, variables: dict):
        calls.append((document, variables))
        if _operation_name(document).startswith("query SetState"):
            return {"set": {"state": 4}}
        if _operation_name(document).startswith("query SetEntrants"):
            return {"set": {"slots": [{"entrant": {"id": "entrant-2"}}, {"entrant": {"id": "entrant-1"}}]}}
        return {"reportBracketSet": {"id": "set-1", "state": 3}}

    client.query = query  # type: ignore[method-assign]
    provider = StartGGProvider(client=client)
    result = await provider.report_score("set-1", "entrant-1", "entrant-1", "entrant-2", 2, 1)

    assert (result.success, result.new_state) == (True, ProviderSetState.COMPLETE)
    assert [_operation_name(document) for document, _ in calls] == [
        "query SetState($id: ID!) {",
        "mutation MarkInProgress($setId: ID!) {",
        "query SetEntrants($id: ID!) {",
        "mutation ReportBracketSet($setId: ID!, $winnerId: ID!, $gameData: [BracketSetGameDataInput!]) {",
    ]
    assert calls[-1][1] == {
        "setId": "set-1", "winnerId": "entrant-1",
        "gameData": [
            {"winnerId": "entrant-2", "entrant1Score": 1, "entrant2Score": 0, "gameNum": 1},
            {"winnerId": "entrant-1", "entrant1Score": 0, "entrant2Score": 1, "gameNum": 2},
            {"winnerId": "entrant-1", "entrant1Score": 0, "entrant2Score": 1, "gameNum": 3},
        ],
    }


@pytest.mark.asyncio
async def test_errors_timeouts_and_unsupported_preview_actions_keep_legacy_outcomes():
    client = StartGGClient(token="fixture")
    client.query = AsyncMock(side_effect=httpx.ReadTimeout("fixture timeout"))  # type: ignore[method-assign]
    provider = StartGGProvider(client=client)

    score = await provider.report_score("set-1", "entrant-1", "entrant-1", "entrant-2", 2, 0)
    preview_call = await provider.mark_called("preview-1")
    preview_active = await provider.mark_in_progress("preview-1")

    assert score.success is False
    assert "markSetInProgress failed" in (score.error_message or "")
    assert (preview_call.success, preview_active.success) == (False, False)
    assert [
        (_operation_name(call.args[0]), call.args[1]) for call in client.query.await_args_list
    ] == [
        ("query SetState($id: ID!) {", {"id": "set-1"}),
        ("mutation MarkInProgress($setId: ID!) {", {"setId": "set-1"}),
    ]


def test_startgg_adapter_sources_never_import_challonge_or_discord_workflows():
    from pathlib import Path

    root = Path(__file__).resolve().parents[4] / "core" / "providers" / "startgg"
    for path in (root / "provider.py", root / "client.py", root / "queries.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert "challonge" not in source
        assert "discord" not in source


@pytest.mark.asyncio
async def test_v2_read_wrapper_reuses_startgg_reads_and_refuses_remote_mutations_before_send():
    client = AsyncMock()
    client.fetch_set_state.return_value = 6
    client.fetch_set_entrant_order.return_value = ["entrant-1", "entrant-2"]
    provider = StartGGProvider(client=client)
    request = ProviderSnapshotRequestV2(
        provider_type="startgg", provider_account_id="test", tournament_id="fixture",
        scope=SnapshotScope.SINGLE_MATCH, entity_ids=frozenset({"set-1"}),
    )

    snapshot = await provider.fetch_snapshot_v2(request)
    result = await provider.execute_remote_command_v2(
        ProviderCommandV2(
            command_id="command-1", provider_type="startgg", provider_account_id="test",
            tournament_id="fixture", provider_match_id="set-1", action="report_score",
            idempotency_key="fixture", payload_digest="fixture",
        )
    )

    assert snapshot.payload == {
        "set_id": "set-1", "state": int(ProviderSetState.CALLED),
        "aitob_state_code": int(ProviderSetState.CALLED),
        "state_source": "aitob", "provider_state_raw": "6",
        "entrant_ids": ["entrant-1", "entrant-2"],
    }
    assert provider.capabilities_v2.for_action("report_score").kind is ProviderActionKind.REMOTE
    assert result.state is ProviderCommandState.NEEDS_REVIEW
    assert result.acknowledged is False
    client.fetch_set_state.assert_awaited_once_with("set-1")
    client.fetch_set_entrant_order.assert_awaited_once_with("set-1")
    client.mark_in_progress.assert_not_called()
    client.mark_set_dq.assert_not_called()
    client.assign_stream.assert_not_called()
