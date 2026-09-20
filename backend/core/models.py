from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from datetime import datetime

class Player(BaseModel):
    discord_id: str
    # Canonical Feature 004 vocabulary. Legacy aliases remain readable at the
    # adapter boundary but are not used by new wizard/registration payloads.
    prefix: Optional[str] = None
    gamertag: Optional[str] = None
    startgg_id: Optional[str] = None
    gamer_tag: Optional[str] = None
    cfn_id: Optional[str] = None
    country: Optional[str] = None
    team: Optional[str] = None
    avatar_path: Optional[str] = None
    is_verified: bool = False
    registration_step: str = "startgg_linked"
    preferred_language: str = "ar"

class Tournament(BaseModel):
    slug: str
    name: str
    event_name: Optional[str] = None
    event_id: Optional[str] = None
    game: Optional[str] = None
    stream_slot: Optional[str] = None
    raw_data: Optional[str] = None
    dq_timer_seconds: int = 600
    provider_dq_timer_seconds: Optional[int] = None
    auto_dq_enabled: bool = False
    bot_manage_limit: Optional[str] = "off"
    bot_manage_finish: Optional[str] = "off"
    registration_deadline: Optional[datetime] = None
    created_at: Optional[datetime] = None

class ActiveMatch(BaseModel):
    set_id: str
    tournament_slug: str
    station_id: Optional[str] = None
    p1_name: str
    p1_score: int = 0
    p2_name: str
    p2_score: int = 0
    p1_entrant_id: Optional[str] = None
    p2_entrant_id: Optional[str] = None
    p1_discord: Optional[str] = None
    p2_discord: Optional[str] = None
    p1_prefix: Optional[str] = None
    p2_prefix: Optional[str] = None
    # Deprecated read aliases for saved overlays created before prefix became
    # the canonical broadcast vocabulary.
    p1_team: Optional[str] = None
    p2_team: Optional[str] = None
    p1_country: Optional[str] = None
    p2_country: Optional[str] = None
    p1_cfn: Optional[str] = None
    p2_cfn: Optional[str] = None
    p1_ready: bool = False
    p2_ready: bool = False
    round_name: Optional[str] = None
    match_number: Optional[int] = None
    swapped: bool = False
    bot_enabled: bool = True
    status: str = "not_started"
    broadcast_state: str = "off_air"
    attendance_protected_at: Optional[datetime] = None
    broadcast_started_at: Optional[datetime] = None
    broadcast_ended_at: Optional[datetime] = None
    dq_player: Optional[str] = None
    phase_group: Optional[str] = ""
    is_stream_match: bool = False
    called_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

class MatchResult(BaseModel):
    id: Optional[int] = None
    set_id: str
    tournament_slug: str
    stream_slot: Optional[str] = None
    p1_name: str
    p2_name: str
    winner: str
    p1_score: str
    p2_score: str
    round_name: Optional[str] = None
    created_at: Optional[datetime] = None

class Conflict(BaseModel):
    id: Optional[int] = None
    set_id: str
    p1_claim: str
    p2_claim: str
    resolved: bool = False
    resolution: Optional[str] = None
    created_at: Optional[datetime] = None

class BotFeedEntry(BaseModel):
    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    message: str
    level: str = "info"

class Overlay(BaseModel):
    id: Optional[int] = None
    name: str
    config: str # JSON string

class HubCommand(BaseModel):
    id: Optional[int] = None
    command_text: str
    status: str = "pending"
    created_at: Optional[datetime] = None

class PlayerOverride(BaseModel):
    id: str
    display_name: Optional[str] = None
    prefix: Optional[str] = None
    team: Optional[str] = None  # Deprecated read alias.
    country: Optional[str] = None
    cfn: Optional[str] = None
    avatar_url: Optional[str] = None
    updated_at: Optional[datetime] = None


# Feature 004 canonical vocabulary and wizard state models.  The legacy models
# above remain readable while migrations are applied; new contracts should use
# these types so `prefix` and `gamertag` cannot be confused with tournament or
# display names.
WizardStep = Literal["provider", "tournament", "discord", "assistant", "review"]
DraftStatus = Literal["editing", "ready", "materialized", "abandoned"]
ReadinessState = Literal["ready", "warning", "blocked"]
ProviderType = Literal["startgg", "challonge"]
ProviderCapabilityState = Literal["supported", "unsupported", "unknown"]
RegistrationState = Literal[
    "awaiting_provider", "awaiting_discord_link", "awaiting_identity",
    "awaiting_image", "awaiting_review", "ready", "rejected", "needs_review",
]
DiscordLinkState = Literal["unlinked", "resolving", "linked", "not_in_guild", "invalid", "conflict"]
ImagePolicy = Literal["disabled", "optional", "required"]


class CanonicalPlayer(BaseModel):
    """Workspace player projection used by new APIs and provider adapters."""

    id: Optional[str] = None
    workspace_id: str
    discord_id: Optional[str] = None
    prefix: Optional[str] = None
    gamertag: str
    country: Optional[str] = None
    image_asset_id: Optional[str] = None
    preferred_language: str = "en"


class ReadinessCheck(BaseModel):
    code: str
    step: WizardStep
    field_path: Optional[str] = None
    requirement: Literal["required", "optional"]
    state: ReadinessState
    message: str
    remediation: Optional[str] = None
    retryable: bool = False


class ProviderCapability(BaseModel):
    state: ProviderCapabilityState
    reason_code: str


class StartInWaveStatus(BaseModel):
    state: Literal["verified_enabled", "verified_disabled", "unsupported", "unknown"]
    observed_at: Optional[datetime] = None
    monitoring_mode: Literal["off", "provider_verified", "organizer_confirmed"] = "off"
    monitoring_state: Literal[
        "not_applicable", "awaiting_bracket_start", "monitoring", "blocked"
    ] = "not_applicable"


class TournamentSetupDraftModel(BaseModel):
    id: str
    workspace_id: str
    revision: int = 1
    status: DraftStatus = "editing"
    current_step: WizardStep = "provider"
    completed_steps: List[WizardStep] = []
    validation: Dict[str, List[ReadinessCheck]] = {}
