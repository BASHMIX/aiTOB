# Role
You are a Lead AI Engineer and Python Architect, an expert in `LangChain`, `LangGraph`, `discord.py` (Async), and building Event-Driven Agentic workflows with LLM Tool Calling.

# Project Context
This is Phase 2 of the AI Tournament Organizer for Street Fighter 6. 
You will build an Event-Driven State Machine using `LangGraph` that manages matches inside Discord threads. 
Because the Agent needs to wait for human input (Discord messages like "ready" or "I won 2-0"), you MUST use LangGraph's Checkpointing (`MemorySaver`) to pause and resume the graph execution.

# Required Tech Stack
- Python 3.10+
- `langgraph` (with `MemorySaver` for persistence)
- `langchain-core`, `langchain-openai` or `langchain-groq` (For LLM)
- `pydantic` (for strict LLM structured output)
- `discord.py`

# Task 1: State Definition (`agent_state.py`)
Define the state schema using `TypedDict`. The graph state must track:
- `set_id` (int): Start.gg match ID.
- `thread_id` (int): Discord thread ID for this match.
- `player1_discord`, `player2_discord` (int): Discord IDs.
- `player1_ready`, `player2_ready` (bool): Default False.
- `chat_history` (list of strings): Formatted as "PlayerX: message".
- `match_status` (str): 'waiting_checkin', 'playing', 'conflict', 'completed', 'dq'.
- `winner_id` (int | None): Resolved winner.
- `score_string` (str | None): e.g., "2-0".

# Task 2: Pydantic Schema for LLM (`schemas.py`)
Create a strict Pydantic model for the LLM to extract results from chat:
```python
class MatchResultExtraction(BaseModel):
    conflict_detected: bool = Field(description="True if players disagree on who won or the score. False if they agree.")
    winner_discord_id: Optional[int] = Field(description="The Discord ID of the winning player, if clear.")
    score: Optional[str] = Field(description="The match score, e.g., '2-0' or '2-1'.")
    reasoning: str = Field(description="Brief explanation of how the LLM determined this outcome based on chat.")