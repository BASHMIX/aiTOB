from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class Player(BaseModel):
    discord_id: str
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
    auto_dq_enabled: bool = True
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
    team: Optional[str] = None
    country: Optional[str] = None
    cfn: Optional[str] = None
    avatar_url: Optional[str] = None
    updated_at: Optional[datetime] = None
