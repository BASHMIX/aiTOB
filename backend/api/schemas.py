from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional, Literal, Dict, List


class CreateActiveMatchRequest(BaseModel):
    set_id: str = Field(description="Start.gg set ID", min_length=1, examples=["12345678"])
    p1_name: str = Field(default="", description="Player 1 name", examples=["AngryBird"])
    p2_name: str = Field(default="", description="Player 2 name", examples=["MenaRD"])
    p1_entrant_id: str = Field(default="", description="Player 1 entrant ID on Start.gg", examples=["987654"])
    p2_entrant_id: str = Field(default="", description="Player 2 entrant ID on Start.gg", examples=["876543"])
    p1_avatar: str = Field(default="", description="Player 1 avatar image URL", examples=["https://avatar.url/p1.png"])
    p2_avatar: str = Field(default="", description="Player 2 avatar image URL", examples=["https://avatar.url/p2.png"])
    round_name: str = Field(default="", description="Tournament round full text description", examples=["Winners Semis"])
    tournament_slug: str = Field(default="", description="Start.gg tournament slug", examples=["tournament/fnc-1st-startgg"])
    match_number: str = Field(default="", description="Identifier or round-group prefix", examples=["A"])
    status: Literal["not_started", "called", "in_progress", "conflict", "complete"] = Field(
        default="not_started", description="Match coordination lifecycle status"
    )
    p1_score: int = Field(default=0, description="Player 1 series score", examples=[2])
    p2_score: int = Field(default=0, description="Player 2 series score", examples=[1])
    phase_group: str = Field(default="", description="Phase group name", examples=["Pool A1"])

    @field_validator("set_id", "p1_entrant_id", "p2_entrant_id", "match_number", "round_name", "phase_group", mode="before")
    @classmethod
    def coerce_str_number(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)


class PatchActiveMatchRequest(BaseModel):
    station_id: Optional[str] = Field(default=None, description="Station ID assignment", examples=["station_1"])
    p1_score: Optional[int] = Field(default=None, description="Updated score for player 1", examples=[2])
    p2_score: Optional[int] = Field(default=None, description="Updated score for player 2", examples=[0])
    swapped: Optional[bool] = Field(default=None, description="Whether player positions are swapped in overlay", examples=[False])
    bot_enabled: Optional[bool] = Field(default=None, description="Whether discord bot manages this match", examples=[True])


class PlayerReadyRequest(BaseModel):
    player: Literal["p1", "p2"] = Field(description="The slot identifier for the player")


class ToggleStreamRequest(BaseModel):
    is_stream_match: bool = Field(default=False, description="Whether this match should display on the OBS broadcast overlay")


class DQRequest(BaseModel):
    player: Literal["p1", "p2", "both"] = Field(description="The entrant slot(s) to disqualify")


class ResolveConflictRequest(BaseModel):
    resolution: str = Field(default="Admin resolved", description="Administrative notes regarding conflict resolution", examples=["Admin manually input MENARD won"])
    p1_score: Optional[int] = Field(
        default=None,
        description="TO-decided final score for player 1. When both scores are provided, the set is completed with this score and reported to the provider (not just annotated).",
        examples=[3],
    )
    p2_score: Optional[int] = Field(
        default=None,
        description="TO-decided final score for player 2. Required alongside p1_score for a full score resolution.",
        examples=[1],
    )
    winner_id: Optional[str] = Field(
        default=None,
        description="Entrant ID of the TO-chosen winner. When provided (without explicit scores), the backend assigns a default 2-0 to the winner, completes the set, and reports it to the provider.",
        examples=["987654"],
    )


class AddTournamentRequest(BaseModel):
    slug: str = Field(description="Start.gg tournament slug or full event URL", examples=["tournament/fnc-1st-startgg/event/street-fighter-6-singles"])


class BotCommandRequest(BaseModel):
    command: str = Field(description="Hub command string to execute in bot loop", examples=["call_match 12345678"])


class CreatePlayerRequest(BaseModel):
    discord_id: str = Field(description="Player Discord ID", examples=["123456789012345678"])
    name: str = Field(default="", description="Player name override", examples=["AngryBird"])
    cfn: str = Field(default="", description="Player CFN ID", examples=["ANGRY_BIRD"])
    team: str = Field(default="", description="Player team tag", examples=["NASR"])


class SaveOverlayRequest(BaseModel):
    name: str = Field(description="Overlay identifier name", examples=["station_1"])
    config: Dict[str, Any] = Field(description="JSON dictionary layout configuration")


class CreateStationRequest(BaseModel):
    id: str = Field(description="Unique station ID (must be at least 1 char)", min_length=1, examples=["station_1"])
    name: str = Field(description="Station display name", min_length=1, examples=["Station 1"])


class UpdateStationRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="Station display name", min_length=1, examples=["Station 1 - Stream"])
    startgg_stream_id: Optional[str] = Field(
        default=None,
        description=(
            "start.gg streamId to push matches on this station onto the public stream queue. "
            "Pass an empty string to unmap. Get valid IDs from GET /api/tournaments/{slug}/streams."
        ),
        examples=["123456", ""],
    )
    stream_url: Optional[str] = Field(
        default=None,
        description="Display-only stream URL override (e.g. https://twitch.tv/foo). Empty string clears.",
        examples=["https://twitch.tv/fnctv", ""],
    )
    bot_enabled: Optional[bool] = Field(
        default=None,
        description="Default for whether the Discord bot announces matches on this station.",
    )
    hidden: Optional[bool] = Field(
        default=None,
        description="Hide this station from the dashboard and auto-assignment round-robin.",
    )
    active_overlay: Optional[str] = Field(
        default=None,
        description="Name of overlay preset to load on this station. Empty string clears.",
    )


class AddStationOverlayRequest(BaseModel):
    overlay_name: str = Field(description="Name of the overlay configuration to link", min_length=1, examples=["default"])


class SetActiveOverlayRequest(BaseModel):
    overlay_name: Optional[str] = Field(default=None, description="Active overlay name (pass null to hide)", examples=["default"])


class PatchSettingsRequest(BaseModel):
    global_language: Optional[str] = Field(default=None, description="Bilingual prompt language setting", examples=["ar"])
    current_theme: Optional[str] = Field(default=None, description="Dashboard theme selection", examples=["pro"])
    registration_msg: Optional[str] = Field(default=None, description="Bot welcome text")
    q_cfn_id: Optional[str] = Field(default=None, description="Custom prompt CFN query")
    q_avatar: Optional[str] = Field(default=None, description="Custom prompt avatar query")
    q_language: Optional[str] = Field(default=None, description="Custom prompt language query")
    bot_system_prompt: Optional[str] = Field(default=None, description="Dynamic system instructions for the LLM referee")
    match_threads_channel_id: Optional[str] = Field(
        default=None,
        description="Discord channel ID where the bot creates per-match threads. If unset, falls back to the first available text channel.",
        examples=["1234567890123456789"],
    )


class PatchEnvRequest(BaseModel):
    STARTGG_API_TOKEN: Optional[str] = Field(default=None, description="Start.gg GraphQL API Bearer Token")
    MATCH_CALL_CHANNEL_ID: Optional[str] = Field(default=None, description="Discord channel ID for bracket callouts")
    STARTGG_CLIENT_ID: Optional[str] = Field(default=None, description="Start.gg OAuth client identifier")
    STARTGG_CLIENT_SECRET: Optional[str] = Field(default=None, description="Start.gg OAuth client secret (required for the OAuth callback to exchange tokens)")
    DISCORD_BOT_TOKEN: Optional[str] = Field(default=None, description="Discord bot token (restart bot process after rotating)")
    API_BASE_URL: Optional[str] = Field(default=None, description="Publicly reachable base URL for the API — used to build OAuth callback links sent to players")
    AI_PROVIDER: Optional[str] = Field(default=None, description="LLM provider configuration (gemini or openai)")
    AI_MODEL: Optional[str] = Field(default=None, description="Exact LLM model slug to run")
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Direct API key override for Google Gemini client")


class CreatePlannedStreamRequest(BaseModel):
    set_id: str = Field(description="Start.gg set ID (real or preview_xxx)", min_length=1, examples=["12345678", "preview_1234567890"])
    tournament_slug: str = Field(description="Start.gg tournament slug this set belongs to", min_length=1, examples=["tournament/fnc-1st-startgg"])
    stream_id: Optional[str] = Field(
        default=None,
        description="Optional start.gg stream ID to prefer. NULL = any free stream / first stream-mapped station.",
        examples=["123456"],
    )
    note: Optional[str] = Field(default=None, description="Optional T.O. note", examples=["Featured match"])


class PlannedStreamsResponse(BaseModel):
    planned: List[Dict[str, Any]] = Field(description="Array of planned-stream entries for this tournament")


class PatchTournamentSettingsRequest(BaseModel):
    dq_timer_seconds: Optional[int] = Field(default=None, description="Number of seconds players have to check in", examples=[600])
    auto_dq_enabled: Optional[bool] = Field(default=None, description="Whether players are auto-DQ'd if timer expires", examples=[True])
    bot_manage_limit: Optional[str] = Field(default=None, description="Which pools or segments are managed by the AI referee", examples=["top8"])
    bot_manage_finish: Optional[str] = Field(default=None, description="Whether matching is finalized automatically", examples=["auto"])
    # Auto-dispatcher controls
    auto_dispatch_enabled: Optional[bool] = Field(
        default=None,
        description="Arm the auto-dispatcher for this tournament. Master switch must also be ON.",
    )
    auto_dispatch_concurrency: Optional[int] = Field(
        default=None, ge=1, le=20,
        description="Max bot-dispatched matches in flight at once (1–20). Start with 1 until trusted.",
        examples=[1, 4],
    )
    auto_dispatch_stop_at: Optional[int] = Field(
        default=None, ge=0, le=64,
        description="When uncompleted matches drop to this number or fewer, dispatcher hands off to TO (typically 8 for Top 8).",
        examples=[8],
    )
    ignore_activity_guard: Optional[bool] = Field(
        default=None,
        description=(
            "Force-load matches even when the tournament/phase isn't ACTIVE on start.gg. "
            "Off by default. For replaying completed brackets or testing — Send/Call may "
            "still fail since start.gg refuses mutations on completed sets."
        ),
    )


class DispatcherMasterRequest(BaseModel):
    enabled: bool = Field(description="Flip the GLOBAL kill switch for the auto-dispatcher.")


# ── Response Schemas ───────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str = Field(description="Operational outcome description", examples=["Success"])
    ok: Optional[bool] = Field(default=None, description="Flag representing binary success/failure status", examples=[True])


class ErrorResponse(BaseModel):
    error: bool = Field(default=True, description="Always true", examples=[True])
    message: str = Field(description="Detailed description of the error", examples=["Authorization header is invalid or expired."])


class ActiveMatchesResponse(BaseModel):
    matches: List[Dict[str, Any]] = Field(description="Array of all active matches currently tracked")


class ConflictsResponse(BaseModel):
    conflicts: List[Dict[str, Any]] = Field(description="Array of matches with conflicting player claims")


class TournamentsResponse(BaseModel):
    tournaments: List[Dict[str, Any]] = Field(description="Array of all registered tournaments")


class BotFeedResponse(BaseModel):
    feed: List[Dict[str, Any]] = Field(description="Collection of recently logged bot actions and events")

