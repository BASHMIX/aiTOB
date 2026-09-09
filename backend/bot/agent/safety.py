"""Safety boundary for the organizer-facing AI assistant.

The assistant may inspect the local Hub projection, but it must never receive a
tool capable of changing a bracket, a match, Discord, or a station. Those
operations belong to explicit organizer controls and their durable workflows.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


ASSISTANT_COMMAND_PREFIX = "ai_assistant "

# Adding a tool here is a security decision, not a chat UI convenience.
READ_ONLY_ASSISTANT_TOOL_NAMES = frozenset({
    "get_active_matches_tool",
    "get_players_tool",
})

ASSISTANT_SYSTEM_PROMPT = """You are aiTOB's Organizer Assistant.
You help a tournament organizer understand the current local tournament state,
explain workflow and provider status, and suggest a safe next action.

You are read-only. You cannot call a match, report a score, disqualify a
player, reopen a match, assign or release a station, or send a Discord message
or announcement. Never claim that you performed one of those actions. When an
organizer asks for an action, explain the appropriate manual control and any
relevant provider limitation. Use only the read-only tools provided to inspect
the local Hub projection. Be concise and make uncertainty explicit.
"""


def select_read_only_assistant_tools(tools: Iterable[Any]) -> list[Any]:
    """Return only explicitly approved read-only LangChain tools."""
    return [tool for tool in tools if getattr(tool, "name", None) in READ_ONLY_ASSISTANT_TOOL_NAMES]


def make_assistant_command(text: str) -> str:
    """Tag a Hub request so the bot cannot treat it as a manual command."""
    return f"{ASSISTANT_COMMAND_PREFIX}{text.strip()}"


def unwrap_assistant_command(command: str) -> str | None:
    """Return assistant input only for a deliberately tagged request."""
    normalized = command.strip()
    if not normalized.lower().startswith(ASSISTANT_COMMAND_PREFIX):
        return None
    message = normalized[len(ASSISTANT_COMMAND_PREFIX):].strip()
    return message or None
