import os
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

from .agent_state import MatchState
from .schemas import MatchResultExtraction

load_dotenv()

# ── Lazy LLM init ────────────────────────────────────────────────────────
# The API key may live in the DB (set via Hub settings) rather than .env.
# We defer instantiation until first use so the DB is already available.
_llm = None
_extractor_llm = None
# Result inference is intentionally unavailable until a durable Result Claims
# workflow exists. Kept explicit so historical benchmark tests do not imply
# that model output is an accepted tournament result.
AI_REFEREE_RESULT_INFERENCE_ENABLED = False

async def _get_llm():
    """Return the LLM, initializing it on first call using the key from DB or env."""
    global _llm, _extractor_llm
    if _llm is not None:
        return _llm, _extractor_llm

    # Try DB first, fall back to env
    api_key = None
    try:
        import sys, os as _os
        root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
        if root not in sys.path:
            sys.path.append(root)
        from backend.core.database import get_setting, get_connection
        api_key = (
            await get_setting("GOOGLE_API_KEY")
            or await get_setting("GEMINI_API_KEY")
            or await get_connection("GOOGLE_API_KEY")
            or await get_connection("GEMINI_API_KEY")
        )
    except Exception:
        pass

    api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "No Gemini API key found. Set GOOGLE_API_KEY in Hub Settings or in your .env file."
        )

    _llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        api_key=api_key,
    )
    _extractor_llm = _llm.with_structured_output(MatchResultExtraction)
    return _llm, _extractor_llm

async def evaluate_chat(state: MatchState) -> dict:
    """Disable legacy AI-referee result inference pending Result Claims.

    A player chat message is not durable evidence and must never become a
    completed/conflict state merely because an LLM parsed it. The Organizer
    Assistant has its own read-only/propose-only service; this legacy graph is
    intentionally inert until a reviewed Result Claim pipeline consumes it.
    """
    return {}

# Build the Graph
workflow = StateGraph(MatchState)

workflow.add_node("evaluate_chat", evaluate_chat)

# Define simple edge logic for the skeleton
workflow.set_entry_point("evaluate_chat")
workflow.add_edge("evaluate_chat", END)

# Compile with memory checkpointing
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

async def process_message(thread_id: int, author_id: int, author_name: str, message_content: str):
    """
    Called by the Discord bot when a message is received in a match thread.
    Returns the new state of the graph.
    """
    config = {"configurable": {"thread_id": str(thread_id)}}
    
    # Get current state to fetch the chat history
    current_state_snapshot = app.get_state(config)
    
    if not current_state_snapshot.values:
        print(f"Warning: No graph state found for thread {thread_id}")
        return None
        
    current_state = current_state_snapshot.values
    
    # Append the new message
    chat_entry = f"{author_name} (ID: {author_id}): {message_content}"
    chat_history = current_state.get("chat_history", [])
    chat_history.append(chat_entry)
    
    # We pass the full updated chat_history into ainvoke, which overrides the state
    new_state = await app.ainvoke({"chat_history": chat_history}, config)
    
    return new_state
