"""AI Discord conflict investigation.

When a match enters `conflict`, the bot DMs both players for their account of
what happened. Their replies are stored as the conflict's p1/p2 claims; once both
are in, this module asks the LLM to compress the dispute into a single neutral
sentence for the tournament organizer (it never picks a winner — that's the TO's
call from the dashboard).
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from bot.agent.hub_agent import _get_api_key

_SYSTEM = (
    "You are a tournament referee assistant for a Street Fighter 6 event. "
    "Two players have a score dispute. Summarize their disagreement in ONE concise, "
    "neutral sentence (max 25 words) for the tournament organizer. State each player's "
    "claim factually. DO NOT decide a winner. "
    "Prefer the form: '<P1> claims X; <P2> claims Y.'"
)


async def summarize_conflict(p1_name: str, p1_claim: str, p2_name: str, p2_claim: str):
    """Return a one-line dispute summary, or None if the LLM is unavailable."""
    api_key = await _get_api_key()
    if not api_key:
        return None
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, api_key=api_key)
        messages = [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=(
                f"Player 1 ({p1_name or 'P1'}) says: {p1_claim or '(no response)'}\n"
                f"Player 2 ({p2_name or 'P2'}) says: {p2_claim or '(no response)'}"
            )),
        ]
        resp = await llm.ainvoke(messages)
        text = (getattr(resp, "content", "") or "").strip()
        return text or None
    except Exception:
        return None
