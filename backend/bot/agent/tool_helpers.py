"""Helpers for shaping data passed to the LLM hub agent.

Kept separate from bot.main so the projection logic is importable/testable
without constructing the Discord client.
"""

# Fields the agent needs to reason about and act on a match. Deliberately EXCLUDES
# discord_thread_id — the LLM was conflating it with set_id and reporting scores
# against the thread id. Score/DQ tools key on set_id, so set_id leads here.
AGENT_MATCH_FIELDS = (
    "set_id",
    "status",
    "event_name",
    "p1_name", "p2_name",
    "p1_entrant_id", "p2_entrant_id",
    "p1_discord", "p2_discord",
    "p1_score", "p2_score",
    "station_id",
)


def project_match_for_agent(match: dict) -> dict:
    """Curated, LLM-safe view of an active match row (no discord_thread_id)."""
    return {k: match.get(k) for k in AGENT_MATCH_FIELDS}
