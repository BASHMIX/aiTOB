"""Pydantic v2 schemas for Tournament Results Media API."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReadinessWarning(BaseModel):
    code: str
    severity: Literal["info", "warning", "blocking"]
    entrant_id: Optional[str] = None
    message: str


class PresentationField(BaseModel):
    value: Any
    source: Literal["entrant_override", "player_profile", "provider_snapshot", "placeholder"]


class CharacterPresentationValue(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    image_url: Optional[str] = None


class FrozenPresentation(BaseModel):
    display_name: PresentationField
    prefix: PresentationField
    country: PresentationField
    avatar_url: PresentationField
    character: PresentationField


class StandingEntry(BaseModel):
    ordinal: int = Field(ge=1)
    placement: int = Field(ge=1)
    entrant_id: str
    entrant_name: str
    provider_user_id: Optional[str] = None
    player_profile_id: Optional[str] = None
    is_tied: bool = False
    presentation: FrozenPresentation


class PageInfo(BaseModel):
    number: int = Field(default=1, ge=1)
    size: int = Field(default=16, ge=1)
    total_entries: int = Field(default=0, ge=0)
    has_more: bool = False


class ResultVersionResponse(BaseModel):
    id: str
    tournament_slug: str
    provider_type: Literal["startgg", "challonge"]
    event_id: str
    event_name: str
    game_id: Optional[str] = None
    game_name: Optional[str] = None
    capture_status: Literal["provisional", "final"]
    readiness_state: Literal["provisional", "final", "stale"]
    provider_state_raw: str
    provider_revision: Optional[str] = None
    observed_at: str
    finalized_at: Optional[str] = None
    entry_count: int = Field(ge=0)
    warnings: List[ReadinessWarning] = Field(default_factory=list)
    page: Optional[PageInfo] = None
    entries: List[StandingEntry] = Field(default_factory=list)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False
    presentation_mode: Literal["current"] = "current"


class RefreshResult(BaseModel):
    version: ResultVersionResponse
    reused: bool
    readiness_state: Literal["provisional", "final", "stale"]


class RefreshFailure(BaseModel):
    readiness_state: Literal["failed"] = "failed"
    code: str
    message: str
    warnings: List[ReadinessWarning] = Field(default_factory=list)


class OutputProfileSchema(BaseModel):
    width: int = Field(ge=320, le=7680)
    height: int = Field(ge=320, le=7680)
    transparent: bool = False


class CreateMediaOutputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_kind: Literal["static", "live"]
    overlay_name: Optional[str] = None
    scene: Dict[str, Any]
    cutoff: Literal["top8", "top16", "all"]
    page_number: int = Field(default=1, ge=1)
    output_profile: OutputProfileSchema


class MediaOutputResponse(BaseModel):
    id: str
    result_version_id: str
    output_kind: Literal["static", "live"]
    scene_hash: str
    cutoff: Literal["top8", "top16", "all"]
    page_number: int = Field(ge=1)
    output_profile: Dict[str, Any]
    created_at: str


class ExportReceiptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    byte_size: int = Field(ge=1, le=52428800)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ExportReceiptResponse(BaseModel):
    output_id: str
    recorded: bool = True


class BindSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_output_id: str
    expected_revision: int = Field(ge=0)


class SessionCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: Literal["take_live", "play_all", "next", "previous", "hold", "restart", "clear"]
    expected_revision: int = Field(ge=0)


class ResultsSessionResponse(BaseModel):
    station_id: str
    media_output_id: Optional[str] = None
    state: Literal["cleared", "ready", "live", "held", "complete", "error"]
    cue_index: int = Field(ge=-1)
    session_revision: int = Field(ge=0)
    error_code: Optional[str] = None
    updated_at: str
