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
    """
    Node that calls the LLM to evaluate the current chat history.
    """
    chat_context = "\n".join(state.get("chat_history", []))

    if not chat_context.strip():
        return {}

    # Explicit roster so the LLM maps winner_discord_id to a REAL player in this
    # match (fixes the "winner didn't match either player" mismatch). The chat
    # lines are tagged "(ID: <discord_id>)", so the model can tie a self-report
    # ("I won 2-1") to the correct Discord ID.
    p1_name = state.get("player1_name") or "Player 1"
    p2_name = state.get("player2_name") or "Player 2"
    p1_did = state.get("player1_discord")
    p2_did = state.get("player2_discord")
    roster = (
        f"Players in this match (winner_discord_id MUST be one of these two Discord IDs):\n"
        f"  • {p1_name} — Discord ID: {p1_did}\n"
        f"  • {p2_name} — Discord ID: {p2_did}\n\n"
    )

    prompt = (
        "Evaluate the following match chat and extract the match result.\n"
        "Look for indications of who won, the score, and if there are any conflicts or disputes.\n"
        "Each chat line is tagged with the sender's Discord ID. Set winner_discord_id to the "
        "Discord ID of the player who WON — it must be exactly one of the two IDs listed below.\n\n"
        f"{roster}"
        f"Chat History:\n{chat_context}"
    )
    
    try:
        _, extractor = await _get_llm()
        result: MatchResultExtraction = extractor.invoke(prompt)
        
        updates = {}
        if result.conflict_detected:
            updates["match_status"] = "conflict"
        elif result.winner_discord_id and result.score:
            updates["match_status"] = "completed"
            updates["winner_id"] = result.winner_discord_id
            updates["score_string"] = result.score

        # Always carry the reasoning forward so callers can log it on status flips.
        if result.reasoning:
            updates["reasoning"] = result.reasoning

        return updates
    except Exception as e:
        print(f"LLM Extraction failed: {e}")
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
