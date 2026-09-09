"""Player and AI result input must never mutate a bracket before Result Claims exist."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _Channel:
    def __init__(self) -> None:
        self.send = AsyncMock()
        self.edit = AsyncMock()


class _Thread(_Channel):
    id = 4100


class _Context:
    def __init__(self, channel: object) -> None:
        self.channel = channel
        self.send = AsyncMock()


class _DMMessage:
    def __init__(self, content: str = "score 2 1") -> None:
        self.author = SimpleNamespace(id=100)
        self.content = content
        self.channel = _Channel()


@pytest.mark.asyncio
async def test_report_command_is_organizer_only_and_never_loads_a_match(monkeypatch):
    """A player command in a match thread is acknowledgement-only, never a mutation."""
    from backend.bot import main

    monkeypatch.setattr(main.discord, "Thread", _Thread)
    ctx = _Context(_Thread())

    await main.report.callback(ctx, 2, 1)

    ctx.send.assert_awaited_once_with(main.PLAYER_RESULT_ORGANIZER_MESSAGE)


@pytest.mark.asyncio
async def test_dm_score_report_does_not_parse_or_persist_a_score(monkeypatch):
    """DM text must not invoke Gemini, provider reporting, or a local score write."""
    from backend.bot import main

    message = _DMMessage("I won 2-1")
    extractor = AsyncMock()
    monkeypatch.setattr(main, "_llm_extract_dm_score", extractor)

    await main.handle_score_report_dm(message)

    extractor.assert_not_awaited()
    message.channel.send.assert_awaited_once_with(main.PLAYER_RESULT_ORGANIZER_MESSAGE)


@pytest.mark.asyncio
async def test_ai_referee_result_state_never_completes_or_locks_thread():
    """Even a forged completed state from the legacy graph is presentation-only."""
    from backend.bot import main

    message = SimpleNamespace(channel=_Thread())
    await main.handle_match_state_update(
        message,
        {"match_status": "completed", "winner_id": "100", "score_string": "2-1"},
        SimpleNamespace(),
    )

    message.channel.send.assert_awaited_once_with(main.PLAYER_RESULT_ORGANIZER_MESSAGE)
    message.channel.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_thread_messages_do_not_invoke_the_legacy_ai_referee(monkeypatch):
    """Thread chat remains usable, but no model evaluates it for a result."""
    from backend.bot import main

    monkeypatch.setattr(main.discord, "Thread", _Thread)
    dispatch_command = AsyncMock()
    monkeypatch.setattr(main.bot, "process_commands", dispatch_command)
    message = SimpleNamespace(author=SimpleNamespace(name="Player"), channel=_Thread(), content="I won 2-1")

    await main.on_message(message)

    assert not hasattr(main, "process_message")
    dispatch_command.assert_awaited_once_with(message)


@pytest.mark.asyncio
async def test_legacy_referee_graph_is_inert_even_if_called_directly(monkeypatch):
    """A future accidental caller cannot receive a completion decision from the graph."""
    from backend.bot.agent import graph

    model_factory = AsyncMock()
    monkeypatch.setattr(graph, "_get_llm", model_factory)

    result = await graph.evaluate_chat({"chat_history": ["Player says: I won 2-1"]})

    assert result == {}
    model_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_ai_score_and_dq_tools_are_explicitly_blocked():
    """Manual Hub actions remain separate; these callable AI tools cannot mutate."""
    from backend.bot import main

    score = await main.force_score_tool.coroutine("set-1", 2, 0)
    dq = await main.dq_player_tool.coroutine("set-1", "p1")

    assert score == main.AI_RESULT_MUTATION_BLOCKED_MESSAGE
    assert dq == main.AI_DQ_MUTATION_BLOCKED_MESSAGE


@pytest.mark.asyncio
async def test_authorized_manual_score_route_still_uses_its_provider_service(monkeypatch):
    """Closing player/AI paths must not disable the authenticated organizer route."""
    from backend.api.routers import matches
    from backend.core.contracts.tournament_types import ProviderSetResult

    match = {
        "set_id": "set-1", "tournament_slug": "organizer-test",
        "p1_entrant_id": "p1", "p2_entrant_id": "p2", "p1_score": 2, "p2_score": 0,
    }
    provider = object()
    report = AsyncMock(return_value=ProviderSetResult(success=True, set_id="set-1"))
    transition = AsyncMock()
    broadcast = AsyncMock()

    monkeypatch.setattr(matches, "get_active_match", AsyncMock(return_value=match))
    monkeypatch.setattr(matches, "_challonge_match", AsyncMock(return_value=False))
    monkeypatch.setattr(matches, "get_provider_for_tournament", AsyncMock(return_value=provider))
    monkeypatch.setattr(matches, "report_score_to_provider", report)
    monkeypatch.setattr(matches, "transition_match", transition)
    monkeypatch.setattr(matches.hub_mgr, "broadcast", broadcast)

    response = await matches.api_send_match("set-1")

    assert response.ok is True
    report.assert_awaited_once_with(
        set_id="set-1", winner_id="p1", p1_id="p1", p2_id="p2",
        p1_score=2, p2_score=0, provider=provider,
    )
    transition.assert_awaited_once_with("set-1", "complete")
