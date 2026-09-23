"""The Organizer Assistant must not be a second path for mutations."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.api.routers import hub
from backend.api.schemas import BotCommandRequest
from backend.bot.agent.safety import (
    ASSISTANT_COMMAND_PREFIX,
    READ_ONLY_ASSISTANT_TOOL_NAMES,
    make_assistant_command,
    select_read_only_assistant_tools,
    unwrap_assistant_command,
)


def test_assistant_allow_list_excludes_every_mutating_tool():
    tools = [
        SimpleNamespace(name="get_active_matches_tool"),
        SimpleNamespace(name="get_players_tool"),
        SimpleNamespace(name="call_match_tool"),
        SimpleNamespace(name="post_announcement_tool"),
        SimpleNamespace(name="dq_player_tool"),
        SimpleNamespace(name="force_score_tool"),
        SimpleNamespace(name="reopen_match_tool"),
        SimpleNamespace(name="audit_registration_tool"),
    ]

    selected = select_read_only_assistant_tools(tools)

    assert {tool.name for tool in selected} == READ_ONLY_ASSISTANT_TOOL_NAMES
    assert not {"call_match_tool", "post_announcement_tool", "dq_player_tool", "force_score_tool", "reopen_match_tool"} & {
        tool.name for tool in selected
    }


def test_assistant_tag_prevents_manual_command_parser_confusion():
    question = "call_match 471045156"

    tagged = make_assistant_command(question)

    assert tagged == f"{ASSISTANT_COMMAND_PREFIX}{question}"
    assert unwrap_assistant_command(tagged) == question
    assert unwrap_assistant_command(question) is None


def test_discord_verify_does_not_target_identities_by_name_similarity():
    import inspect
    from backend.bot import main

    source = inspect.getsource(main._verify_with_disambiguation)
    assert "_collect_candidate_entrants_async" not in source
    assert "_llm_rank_entrants" not in source
    assert "organizer-confirmed entrant link" in source


@pytest.mark.asyncio
async def test_legacy_assistant_path_rejects_unscoped_input_without_touching_discord(monkeypatch):
    connection = SimpleNamespace(send_text=AsyncMock())
    monkeypatch.setattr(hub.hub_mgr, "bot_connection", connection)
    monkeypatch.setattr(hub.hub_mgr, "broadcast", AsyncMock())
    monkeypatch.setattr(hub, "add_bot_feed", AsyncMock())

    with pytest.raises(HTTPException) as exc:
        await hub.api_hub_command(BotCommandRequest(command="call_match 471045156"))
    assert exc.value.status_code == 400
    connection.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_player_read_tool_cannot_use_process_global_workspace(monkeypatch):
    """The shared bot's legacy assistant tool cannot enumerate tenant data."""
    from backend.bot import main
    import core.database as bot_database

    reader = AsyncMock(return_value=[{"discord_id": "player-a"}])
    monkeypatch.setattr(bot_database, "get_players_for_workspace", reader)
    result = await main.get_players_tool.ainvoke({})

    assert result == "[]"
    reader.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_bot_endpoint_durably_queues_workspace_scoped_command(monkeypatch):
    connection = SimpleNamespace(send_text=AsyncMock())
    monkeypatch.setattr(hub.hub_mgr, "bot_connection", connection)
    monkeypatch.setattr(hub.hub_mgr, "broadcast", AsyncMock())
    monkeypatch.setattr(hub, "add_bot_feed", AsyncMock())
    enqueue = AsyncMock()
    monkeypatch.setattr(hub, "add_hub_command", enqueue)

    principal = SimpleNamespace(workspace_id="workspace-a")
    response = await hub.api_bot_command(
        BotCommandRequest(command="call_match 471045156"), principal=principal,
    )

    import json
    delivered = json.loads(connection.send_text.await_args.args[0])
    assert response.ok is True
    assert delivered == {"type": "drain"}
    enqueue.assert_awaited_once_with("call_match 471045156", workspace_id="workspace-a")


@pytest.mark.asyncio
async def test_legacy_ai_announcement_and_reopen_entrypoints_are_non_mutating():
    """The previously uncovered legacy tools must not send or mutate anything."""
    from backend.bot.main import call_match_tool, post_announcement_tool, reopen_match_tool

    call = await call_match_tool.ainvoke({"set_id": "set-1"})
    announcement = await post_announcement_tool.ainvoke({"announcement_text": "announce this"})
    reopen = await reopen_match_tool.ainvoke({"set_id": "set-1"})
    assert "cannot call matches" in call
    assert "cannot send announcements" in announcement
    assert "cannot reopen matches" in reopen
