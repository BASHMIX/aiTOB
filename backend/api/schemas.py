from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any, Optional, Literal, Dict, List


class ProviderFeatureFlagsResponse(BaseModel):
    """Non-secret product rollout diagnostics."""
    challonge_read_enabled: bool = False
    challonge_local_workflow_enabled: bool = False
    challonge_score_commands_enabled: bool = False
    challonge_dq_commands_enabled: bool = False


class SetupDraftResponse(BaseModel):
    """Safe, resumable Tournament Setup projection returned to the browser."""

    id: str
    workspace_id: str
    revision: int = Field(ge=0)
    status: Literal["editing", "ready", "materialized", "abandoned"]
    current_step: Literal["provider", "tournament", "discord", "assistant", "review"]
    completed_steps: List[Literal["provider", "tournament", "discord", "assistant", "review"]] = Field(default_factory=list)
    provider_scope: Optional[Dict[str, Any]] = None
    tournament_review: Dict[str, Any] = Field(default_factory=dict)
    operating_profile: Dict[str, Any] = Field(default_factory=dict)
    discord_setup: Dict[str, Any] = Field(default_factory=dict)
    assistant_setup: Dict[str, Any] = Field(default_factory=dict)
    validation: Dict[str, Any] = Field(default_factory=dict)
    materialized_tournament_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SetupDraftSectionPatch(BaseModel):
    section: Literal[
        "provider_scope", "tournament_review", "operating_profile",
        "discord_setup", "assistant_setup", "navigation",
    ]
    value: Dict[str, Any] = Field(default_factory=dict)
    current_step: Optional[Literal["provider", "tournament", "discord", "assistant", "review"]] = None


class RegistrationConfigRequest(BaseModel):
    """Safe organizer-controlled tournament registration policy."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    destination_external_id: Optional[str] = Field(default=None, max_length=100)
    opens_at: Optional[str] = Field(default=None, max_length=64)
    closes_at: Optional[str] = Field(default=None, max_length=64)
    display_timezone: str = Field(default="UTC", min_length=1, max_length=100)
    require_provider_registration: bool = True
    gamertag_verification_policy: Literal[
        "exact_discord_name", "set_server_nickname", "match_or_set_nickname",
    ] = "match_or_set_nickname"
    startgg_bio_verification_enabled: bool = False
    image_policy: Literal["disabled", "optional", "required"] = "optional"
    verified_role_external_id: Optional[str] = Field(default=None, max_length=100)
    announcement_policy: Dict[str, Any] = Field(default_factory=dict)


class ManualDiscordLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    discord_user_id: str = Field(pattern=r"^[0-9]{17,20}$")


class RegistrationStateActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Optional[str] = Field(default=None, max_length=500)


class ProviderScopeResolveRequest(BaseModel):
    revision: int = Field(ge=0)
    provider_account_id: str = Field(min_length=1, max_length=100)
    locator: str = Field(min_length=1, max_length=1000)
    challonge_subdomain: Optional[str] = Field(default=None, max_length=100)


class ProviderScopeSelectRequest(BaseModel):
    revision: int = Field(ge=0)
    external_scope_id: str = Field(min_length=1, max_length=300)


class ProviderStateProjectionV2(BaseModel):
    """Dark API model only; no Phase 2 route exposes or consumes it."""

    provider_state: Optional[str] = None
    hub_status: Optional[str] = None
    sync_status: Optional[str] = None
    provider_revision: Optional[str] = None
    observed_at: Optional[str] = None


class DiscordWorkflowProjectionV2(BaseModel):
    call_message_id: Optional[str] = None
    thread_id: Optional[str] = None
    called_at: Optional[str] = None
    player1_ready_at: Optional[str] = None
    player2_ready_at: Optional[str] = None
    attendance_deadline: Optional[str] = None
    last_notification_at: Optional[str] = None


class ProviderFreshnessProjectionV2(BaseModel):
    last_provider_sync: Optional[str] = None
    data_freshness: Optional[str] = None
    sync_available: bool = False


class ProviderCommandSummaryV2(BaseModel):
    command_id: str
    action: str
    state: str
    reason: Optional[str] = None


class ProviderActionProjectionV2(BaseModel):
    action: str
    availability: Literal["remote", "local", "unavailable"]
    reason: Optional[str] = None


class ProviderCapabilityProfileResponse(BaseModel):
    provider_type: str
    display_name: str
    provider_tournament_id: Optional[str] = None
    provider_subdomain: Optional[str] = None
    contract_version: Literal["legacy", "v2"]
    actions: List[ProviderActionProjectionV2] = Field(default_factory=list)
    supports_incremental_sync: Optional[bool] = None
    supports_targeted_match_fetch: Optional[bool] = None
    supports_remote_revision: Optional[bool] = None
    supports_idempotency: Optional[bool] = None


class ChallongeResolveRequest(BaseModel):
    provider_account_id: str = Field(min_length=1, max_length=100)
    identifier: str = Field(min_length=1, max_length=500)
    subdomain: Optional[str] = Field(default=None, max_length=100)


class ChallongeResolveResponse(BaseModel):
    provider_type: Literal["challonge"]
    provider_account_id: str
    provider_tournament_id: str
    name: str
    subdomain: Optional[str] = None
    url_slug: Optional[str] = None
    state: Optional[str] = None
    format: Optional[str] = None
    locator_key: str
    tournament_slug: Optional[str] = None
    cached: bool = False


class ChallongeConnectionStateResponse(BaseModel):
    enabled: bool
    connected: bool


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


class AttendanceRequest(BaseModel):
    player: Literal["p1", "p2"] = Field(description="The entrant slot whose attendance changes")
    state: Literal["present", "withdrawn"] = Field(description="The entrant's called-window attendance intent")


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
    slug: Optional[str] = Field(default=None, description="Start.gg tournament slug or full event URL")
    provider_type: Literal["startgg", "challonge"] = "startgg"
    identifier: Optional[str] = Field(default=None, description="Provider tournament ID, slug, or URL")
    provider_account_id: Optional[str] = Field(default=None, description="Account-scoped provider binding required for Challonge")
    subdomain: Optional[str] = Field(default=None, description="Optional Challonge community/subdomain")


class BotCommandRequest(BaseModel):
    command: str = Field(description="Hub command string to execute in bot loop", examples=["call_match 12345678"])


class CreatePlayerRequest(BaseModel):
    discord_id: str = Field(description="Player Discord ID", examples=["123456789012345678"])
    name: str = Field(default="", description="Player name override", examples=["AngryBird"])
    cfn: str = Field(default="", description="Player CFN ID", examples=["ANGRY_BIRD"])
    team: str = Field(default="", description="Player team tag", examples=["NASR"])


class TournamentPlayerLinkRequest(BaseModel):
    tournament_slug: str = Field(min_length=1, description="Locally tracked tournament slug")
    entrant_id: str = Field(min_length=1, description="Provider entrant/participant ID within that tournament")
    # A confirmed link is now profile-first.  ``discord_id`` remains accepted
    # for the established Discord-player workflow while old tournament links
    # are migrated gradually.
    player_profile_id: Optional[str] = Field(default=None, min_length=1, description="Persistent aiTOB player profile")
    discord_id: Optional[str] = Field(default=None, min_length=1, description="Existing aiTOB player Discord ID")


class SaveOverlayRequest(BaseModel):
    name: str = Field(description="Overlay identifier name", examples=["station_1"])
    config: Dict[str, Any] = Field(description="JSON dictionary layout configuration")


class CreateStationRequest(BaseModel):
    id: str = Field(description="Unique station ID (must be at least 1 char)", min_length=1, examples=["station_1"])
    name: str = Field(description="Station display name", min_length=1, examples=["Station 1"])


class BroadcastPreviewRequest(BaseModel):
    """Select an existing not-started match for local broadcast preview."""
    set_id: str = Field(description="Existing local active match set ID", min_length=1)


class UpdateStationRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="Station display name", min_length=1, examples=["Station 1 - Stream"])
    event_id: Optional[str] = Field(
        default=None,
        description=(
            "Bind this station to a single start.gg event (game). Stream matches are "
            "only routed here when station.event_id == match.event_id. Empty string unbinds."
        ),
        examples=["123456", ""],
    )
    is_stream_station: Optional[bool] = Field(
        default=None,
        description="Mark this as a broadcaster setup eligible to host stream-flagged matches via the green-room flow.",
    )
    room_name_or_id: Optional[str] = Field(
        default=None,
        description="Broadcaster lobby name/ID delivered to players (by DM) only after both check in. Empty string clears.",
        examples=["FNC-STREAM-1", ""],
    )
    room_password: Optional[str] = Field(
        default=None,
        description="Broadcaster lobby password delivered to players (by DM) only after both check in. Empty string clears.",
        examples=["1234", ""],
    )
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


class IssueOverlayAccessRequest(BaseModel):
    """Optional fixed-slide scope for a revocable Browser Source link."""
    overlay_name: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Pin the link to one overlay associated with the station; omit to follow the active slide.",
    )


class SetActiveOverlayRequest(BaseModel):
    overlay_name: Optional[str] = Field(default=None, description="Active overlay name (pass null to hide)", examples=["default"])


class EnqueueMatchRequest(BaseModel):
    set_id: str = Field(description="Set ID to enqueue to station", min_length=1)


class ReorderQueueRequest(BaseModel):
    set_ids: list[str] = Field(description="List of set IDs in new order")


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
    CHALLONGE_API_KEY: Optional[str] = Field(default=None, description="Challonge v1 API key used with v2.1 headers")
    CHALLONGE_OAUTH_CLIENT_ID: Optional[str] = Field(default=None, description="Challonge OAuth application client ID")
    CHALLONGE_OAUTH_CLIENT_SECRET: Optional[str] = Field(default=None, description="Challonge OAuth application client secret")
    CHALLONGE_OAUTH_REDIRECT_URI: Optional[str] = Field(default=None, description="Exact HTTPS callback URL configured in Challonge")
    MATCH_CALL_CHANNEL_ID: Optional[str] = Field(default=None, description="Discord channel ID for bracket callouts")
    STARTGG_CLIENT_ID: Optional[str] = Field(default=None, description="Start.gg OAuth client identifier")
    STARTGG_CLIENT_SECRET: Optional[str] = Field(default=None, description="Start.gg OAuth client secret (required for the OAuth callback to exchange tokens)")
    DISCORD_BOT_TOKEN: Optional[str] = Field(default=None, description="Discord bot token (restart bot process after rotating)")
    API_BASE_URL: Optional[str] = Field(default=None, description="Publicly reachable base URL for the API — used to build OAuth callback links sent to players")
    AI_PROVIDER: Optional[str] = Field(default=None, description="LLM provider configuration (gemini or openai)")
    AI_MODEL: Optional[str] = Field(default=None, description="Exact LLM model slug to run")
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Direct API key override for Google Gemini client")
    CLOUDINARY_URL: Optional[str] = Field(default=None, description="Cloudinary URL (cloudinary://key:secret@cloud) for broadcast avatar hosting. If unset, avatars save locally under /static.")


class AIServiceConfigRequest(BaseModel):
    provider_type: Optional[Literal["gemini", "openai"]] = None
    model: Optional[str] = Field(default=None, min_length=1, max_length=160)
    mode: Optional[Literal["disabled", "read_only", "propose_only"]] = None
    request_limit: Optional[int] = Field(default=None, ge=1, le=10_000)
    token_limit: Optional[int] = Field(default=None, ge=256, le=20_000_000)
    context_char_limit: Optional[int] = Field(default=None, ge=512, le=100_000)
    response_char_limit: Optional[int] = Field(default=None, ge=128, le=20_000)
    request_timeout_seconds: Optional[int] = Field(default=None, ge=3, le=120)
    policy_version: Optional[str] = Field(default=None, min_length=1, max_length=120)


class AIServiceSecretRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=10_000)


class AIAssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class AIConnectionTestRequest(BaseModel):
    model: Optional[str] = Field(default=None, min_length=1, max_length=160)


class IntegrationAccountRequest(BaseModel):
    provider_type: str = Field(pattern="^(discord|challonge|startgg)$")
    external_account_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IntegrationCredentialRequest(BaseModel):
    secret_type: str = Field(pattern="^(bot_token|api_key|access_token|refresh_token)$")
    secret: str = Field(min_length=1)


class IntegrationDestinationRequest(BaseModel):
    destination_type: str = Field(pattern="^(match_call_channel)$")
    external_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(default="", max_length=200)


class IntegrationOAuthApplicationRequest(BaseModel):
    provider_type: str = Field(pattern="^challonge$")
    client_id: str = Field(min_length=1, max_length=500)
    redirect_uri: str = Field(min_length=8, max_length=1000)
    client_secret: str = Field(min_length=1)


class ProviderIdentityLinkRequest(BaseModel):
    provider_type: str = Field(pattern="^(challonge|startgg)$")
    tournament_slug: str = Field(min_length=1, max_length=300)
    provider_participant_id: Optional[str] = Field(default=None, max_length=200)
    provider_entrant_id: str = Field(min_length=1, max_length=200)
    discord_user_id: str = Field(min_length=1, max_length=200)


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
    accent_color: Optional[str] = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Tournament-scoped Hub accent colour, in #RRGGBB form.",
        examples=["#60A5FA"],
    )
    dq_timer_seconds: Optional[int] = Field(default=None, description="Number of seconds players have to check in", examples=[600])
    provider_dq_timer_seconds: Optional[int] = Field(
        default=None, ge=15, le=7200,
        description=(
            "Organizer-verified mirror of Start.gg's per-match DQ timer. "
            "The public Start.gg API does not expose this round setting."
        ),
        examples=[60, 600],
    )
    auto_dq_enabled: Optional[bool] = Field(
        default=None,
        description="Legacy local timer switch. Start.gg bracket outcomes remain provider-owned.",
        examples=[False],
    )
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
    auto_dispatch_on_stream: Optional[bool] = Field(
        default=None,
        description="Allow automatic Calls for on-stream matches. Off by default so featured matches stay under TO control.",
    )
    ignore_activity_guard: Optional[bool] = Field(
        default=None,
        description=(
            "Force-load matches even when the tournament/phase isn't ACTIVE on start.gg. "
            "Off by default. For replaying completed brackets or testing — Send/Call may "
            "still fail since start.gg refuses mutations on completed sets."
        ),
    )
    check_in_source: Optional[str] = Field(
        default=None,
        description=(
            "Where attendance is confirmed. 'discord' lets verified Discord/manual controls record "
            "each entrant while Start.gg owns the called deadline and bracket outcome. 'startgg' "
            "uses Start.gg's native check-in surface."
        ),
        examples=["discord", "startgg"],
    )
    challonge_sync_mode: Optional[str] = Field(
        default=None,
        description="Challonge synchronization policy: economy (manual plus post-score batch) or live (periodic).",
        examples=["economy", "live"],
    )
    economy_sync_on_stale_open: Optional[bool] = Field(
        default=None,
        description="In Economy mode, permit one background Challonge refresh when a stale dashboard opens.",
    )

    @field_validator("check_in_source")
    @classmethod
    def _validate_check_in_source(cls, v):
        if v is not None and v not in ("discord", "startgg"):
            raise ValueError("check_in_source must be 'discord' or 'startgg'")
        return v

    @field_validator("challonge_sync_mode")
    @classmethod
    def _validate_challonge_sync_mode(cls, v):
        if v is not None and v not in ("economy", "live"):
            raise ValueError("challonge_sync_mode must be 'economy' or 'live'")
        return v


class DispatcherMasterRequest(BaseModel):
    enabled: bool = Field(description="Flip the GLOBAL kill switch for the auto-dispatcher.")


class ChallongeStateRepairDryRunRequest(BaseModel):
    """Immutable provider evidence supplied by a prior, reviewed snapshot."""
    snapshot_id: str = Field(min_length=1)
    snapshot_observed_at: str = Field(min_length=1)
    provider_states: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class CreateActionProposalRequest(BaseModel):
    tournament_slug: str = Field(min_length=1, max_length=300)
    action_type: Literal["call", "announcement_draft"]
    match_id: Optional[str] = Field(default=None, max_length=300)
    payload: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=1000)
    expires_in_seconds: int = Field(default=900, ge=60, le=86_400)


class RejectActionProposalRequest(BaseModel):
    reason: str = Field(default="Rejected by organizer", min_length=1, max_length=1000)


# ── Response Schemas ───────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str = Field(description="Operational outcome description", examples=["Success"])
    ok: Optional[bool] = Field(default=None, description="Flag representing binary success/failure status", examples=[True])


class ErrorResponse(BaseModel):
    error: bool = Field(default=True, description="Always true", examples=[True])
    message: str = Field(description="Detailed description of the error", examples=["Authorization header is invalid or expired."])


class ProviderStateAxisResponse(BaseModel):
    """Provider facts, distinct from Hub workflow and synchronization health."""

    raw: Optional[str] = None
    normalized: Optional[str] = None


class MatchStateAxesResponse(BaseModel):
    provider: ProviderStateAxisResponse
    hub_status: Optional[str] = None
    sync_status: Optional[str] = None


class DiscordWorkflowDisplayResponse(BaseModel):
    """Persisted Discord facts only; no inferred delivery status is exposed."""

    call_sent: bool = False
    call_message_id: Optional[str] = None
    thread_id: Optional[str] = None
    called_at: Optional[str] = None
    player1_ready_at: Optional[str] = None
    player2_ready_at: Optional[str] = None
    attendance_deadline: Optional[str] = None


class MatchEligibilityResponse(BaseModel):
    two_sided: bool
    actionable: bool
    reason: Optional[str] = None


class ActiveMatchDisplayResponse(BaseModel):
    """Additive display envelope; legacy match fields pass through unchanged."""

    model_config = ConfigDict(extra="allow")

    v2_available: bool = False
    legacy_status: Optional[str] = None
    state_axes: Optional[MatchStateAxesResponse] = None
    discord: Optional[DiscordWorkflowDisplayResponse] = None
    eligibility: Optional[MatchEligibilityResponse] = None
    provider_diagnostics: Optional[Dict[str, Any]] = None
    progression: Optional[Dict[str, Any]] = None


class ActiveMatchesResponse(BaseModel):
    matches: List[ActiveMatchDisplayResponse] = Field(description="Array of all active matches currently tracked")


class ConflictsResponse(BaseModel):
    conflicts: List[Dict[str, Any]] = Field(description="Array of matches with conflicting player claims")


class TournamentsResponse(BaseModel):
    tournaments: List[Dict[str, Any]] = Field(description="Array of all registered tournaments")


class BotFeedResponse(BaseModel):
    feed: List[Dict[str, Any]] = Field(description="Collection of recently logged bot actions and events")


from backend.core.contracts.player_presentation import (
    CharacterValue,
    EntrantPresentationRequest,
    EntrantScope,
    PlayerPresentationV1,
    PresentationField,
    ResolvedPresentation,
)


class ParticipantPresentationResponse(BaseModel):
    presentations: List[PlayerPresentationV1] = Field(
        default_factory=list,
        description="Resolved presentation models for tournament entrants",
    )
