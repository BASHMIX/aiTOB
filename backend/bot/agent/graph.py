from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI

from .agent_state import MatchState
from .schemas import MatchResultExtraction

# ── Workspace-owned lazy LLM init ────────────────────────────────────────
# The legacy graph is retained for match-thread compatibility, but it must use
# the authenticated workspace's selected BYOK account.  There is deliberately
# no process-global key, environment fallback, or cross-workspace LLM cache.
# Result inference is intentionally unavailable until a durable Result Claims
# workflow exists. Kept explicit so historical benchmark tests do not imply
# that model output is an accepted tournament result.
AI_REFEREE_RESULT_INFERENCE_ENABLED = False

async def _get_llm(workspace_id: str | None = None):
    """Return the selected workspace Gemini LLM and result extractor.

    ``workspace_id`` is required even though the result-referee graph is
    currently inert. Requiring it here prevents a future graph node or legacy
    caller from silently falling back to a platform/global credential.
    """
    from backend.core.ai_service import (
        AIConfigurationError,
        _workspace_api_key,
        get_workspace_ai_config,
    )

    if not workspace_id or not str(workspace_id).strip():
        raise AIConfigurationError("An authenticated workspace is required for AI use.")
    config = await get_workspace_ai_config(str(workspace_id))
    if config.get("mode") == "disabled":
        raise AIConfigurationError("Organizer Assistant is disabled.")
    if config.get("provider_type") != "gemini":
        # The match-thread graph requires Gemini's LangChain structured output
        # object. Workspace OpenAI requests use the provider-neutral
        # ``backend.core.ai_service.AIService`` path instead of an implicit
        # Gemini fallback.
        raise AIConfigurationError("The match assistant graph requires the selected Gemini connection.")
    api_key = await _workspace_api_key(str(workspace_id), config)

    llm = ChatGoogleGenerativeAI(
        model=str(config.get("model") or "gemini-2.5-flash"),
        temperature=0,
        api_key=api_key,
    )
    extractor_llm = llm.with_structured_output(MatchResultExtraction)
    return llm, extractor_llm

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

async def process_message(
    thread_id: int,
    author_id: int,
    author_name: str,
    message_content: str,
    *,
    workspace_id: str | None = None,
):
    """
    Called by the Discord bot when a message is received in a match thread.
    Returns the new state of the graph.
    """
    config = {"configurable": {"thread_id": str(thread_id)}}
    if workspace_id:
        config["configurable"]["workspace_id"] = str(workspace_id)
    
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
