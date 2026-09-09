import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv
from .safety import ASSISTANT_SYSTEM_PROMPT

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

    return create_react_agent(llm, tools, prompt=ASSISTANT_SYSTEM_PROMPT)

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
        return create_react_agent(llm, tools, prompt=ASSISTANT_SYSTEM_PROMPT)

    # Otherwise return None — main.py must call build_hub_agent_async() after on_ready
    return None
