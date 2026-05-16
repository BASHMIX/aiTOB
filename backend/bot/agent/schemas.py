from pydantic import BaseModel, Field
from typing import Optional

class MatchResultExtraction(BaseModel):
    conflict_detected: bool = Field(
        description="True if players disagree on who won or the score. False if they agree."
    )
    winner_discord_id: Optional[int] = Field(
        description="The Discord ID of the winning player, if clear."
    )
    score: Optional[str] = Field(
        description="The match score, e.g., '2-0' or '2-1'."
    )
    reasoning: str = Field(
        description="Brief explanation of how the LLM determined this outcome based on chat."
    )
