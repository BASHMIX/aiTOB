from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional


class CreateActiveMatchRequest(BaseModel):
    set_id: str = Field(description="Start.gg set ID")
    p1_name: str = ""
    p2_name: str = ""
    p1_entrant_id: str = ""
    p2_entrant_id: str = ""
    p1_avatar: str = ""
    p2_avatar: str = ""
    round_name: str = ""
    tournament_slug: str = ""
    match_number: str = ""
    status: str = "not_started"
    p1_score: int = 0
    p2_score: int = 0
    phase_group: str = ""

    @field_validator("set_id", "p1_entrant_id", "p2_entrant_id", "match_number", "round_name", "phase_group", mode="before")
    @classmethod
    def coerce_str_number(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)


class PlayerReadyRequest(BaseModel):
    player: str = Field(description='"p1" or "p2"')


class ToggleStreamRequest(BaseModel):
    is_stream_match: bool = False


class DQRequest(BaseModel):
    player: str = Field(description='"p1", "p2", or "both"')


class ResolveConflictRequest(BaseModel):
    resolution: str = "Admin resolved"


class AddTournamentRequest(BaseModel):
    slug: str = Field(description="Start.gg tournament slug or URL")


class BotCommandRequest(BaseModel):
    command: str = Field(description="Hub command to execute")


class CreatePlayerRequest(BaseModel):
    discord_id: str
    name: str = ""
    cfn: str = ""
    team: str = ""


class SaveOverlayRequest(BaseModel):
    name: str
    config: dict[str, Any]


class CreateStationRequest(BaseModel):
    id: str
    name: str


class UpdateStationRequest(BaseModel):
    name: str


class AddStationOverlayRequest(BaseModel):
    overlay_name: str


class SetActiveOverlayRequest(BaseModel):
    overlay_name: Optional[str] = None


class PatchSettingsRequest(BaseModel):
    settings: dict[str, str]


class MessageResponse(BaseModel):
    message: str
    ok: Optional[bool] = None


class ErrorResponse(BaseModel):
    error: bool = True
    message: str
