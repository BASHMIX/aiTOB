import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from dotenv import load_dotenv

load_dotenv()

async def _get_api_key() -> str:
    """Return the Gemini API key from DB (Hub Settings) or fall back to env."""
    try:
        import sys, os as _os
        root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
        if root not in sys.path:
            sys.path.append(root)
        from backend.core.database import get_setting, get_connection
        key = (
            await get_setting("GOOGLE_API_KEY")
            or await get_setting("GEMINI_API_KEY")
            or await get_connection("GOOGLE_API_KEY")
            or await get_connection("GEMINI_API_KEY")
        )
        if key:
            return key
    except Exception:
        pass
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""

async def build_hub_agent_async(tools):
    """Async version of build_hub_agent — reads API key from DB on first call."""
    api_key = await _get_api_key()
    if not api_key:
        raise RuntimeError(
            "No Gemini API key found. Set GOOGLE_API_KEY in Hub Settings or in your .env file."
        )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        api_key=api_key,
    )

    system_prompt = """You are the 'Hub Agent', an AI Tournament Manager for a Street Fighter 6 tournament.
You receive natural language commands from the tournament organizer via the dashboard.
Your job is to execute these commands by using the tools provided to you.

You have access to a rich set of tools:
1. get_active_matches_tool: List active matches with their set_ids, players, scores, and statuses.
2. get_players_tool: List registered players with their gamer tags and Discord IDs.
3. create_discord_thread_tool: Call players and start a match by creating a Discord thread.
4. post_announcement_tool: Announce a message to the public Discord channel.
5. dq_player_tool: Disqualify a player in a match (e.g. 'p1', 'p2', or 'both').
6. force_score_tool: Manually set match scores and complete a match.
7. reopen_match_tool: Reset and reopen a completed match so it can be re-played or corrected.

Guidelines for actions:
- To call a match: Lookup active matches to find the details, lookup players to get their Discord IDs, then call create_discord_thread_tool.
- To disqualify a player: Use dq_player_tool with the appropriate set_id and player target ('p1', 'p2', or 'both').
- To force/submit a score: Use force_score_tool with the correct scores.
- To reopen a match: Use reopen_match_tool.
- To make a global announcement: Use post_announcement_tool.

Always reply with a clear, concise summary of what you did and the tool execution results.
"""

    return create_react_agent(llm, tools, prompt=system_prompt)

def build_hub_agent(tools):
    """Sync shim kept for backwards-compatibility. Returns a lazy async wrapper."""
    import asyncio

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""

    # If we have an env key right now, build synchronously (fast path)
    if api_key:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            api_key=api_key,
        )
        system_prompt = """You are the 'Hub Agent', an AI Tournament Manager for a Street Fighter 6 tournament.
You receive natural language commands from the tournament organizer via the dashboard.
Your job is to execute these commands by using the tools provided to you.

You have access to a rich set of tools:
1. get_active_matches_tool: List active matches with their set_ids, players, scores, and statuses.
2. get_players_tool: List registered players with their gamer tags and Discord IDs.
3. create_discord_thread_tool: Call players and start a match by creating a Discord thread.
4. post_announcement_tool: Announce a message to the public Discord channel.
5. dq_player_tool: Disqualify a player in a match (e.g. 'p1', 'p2', or 'both').
6. force_score_tool: Manually set match scores and complete a match.
7. reopen_match_tool: Reset and reopen a completed match so it can be re-played or corrected.

Guidelines for actions:
- To call a match: Lookup active matches to find the details, lookup players to get their Discord IDs, then call create_discord_thread_tool.
- To disqualify a player: Use dq_player_tool with the appropriate set_id and player target ('p1', 'p2', or 'both').
- To force/submit a score: Use force_score_tool with the correct scores.
- To reopen a match: Use reopen_match_tool.
- To make a global announcement: Use post_announcement_tool.

Always reply with a clear, concise summary of what you did and the tool execution results.
"""
        return create_react_agent(llm, tools, prompt=system_prompt)

    # Otherwise return None — main.py must call build_hub_agent_async() after on_ready
    return None
