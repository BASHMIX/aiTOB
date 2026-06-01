from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
from enum import IntEnum

class ProviderSetState(IntEnum):
    """Provider-agnostic match states.
    
    Each provider maps its internal states to these canonical values.
    The sync engine and state machine operate exclusively on these.
    """
    NOT_STARTED = 1
    CALLED      = 2
    IN_PROGRESS = 3
    COMPLETE    = 4
    INVALID     = 5   # bye / DQ'd set — skip
    QUEUED      = 6

@dataclass(frozen=True)
class ProviderEntrant:
    """A player/team within a bracket."""
    id: str                                # Provider's entrant ID (opaque string)
    name: str
    avatar_url: Optional[str] = None
    # Cross-event provider account ID (start.gg user.id). Optional because some
    # entrants are T.O.-added by name with no linked user. Used by the hub to
    # resolve the player's Discord ID via the players table.
    user_id: Optional[str] = None

@dataclass(frozen=True)
class ProviderSet:
    """A single match/set in a bracket.
    
    This is the unified contract that all providers must produce.
    The sync engine (database.sync_active_matches) consumes this.
    """
    id: str                                # Provider's set ID
    state: ProviderSetState
    round_name: str = ""
    identifier: Optional[str] = None       # Match number / letter
    phase_group: str = ""
    entrant1: Optional[ProviderEntrant] = None
    entrant2: Optional[ProviderEntrant] = None

@dataclass(frozen=True)
class ProviderEvent:
    """An event within a tournament (e.g., 'Street Fighter 6 Singles')."""
    id: str
    name: str
    game: Optional[str] = None
    entrants: List[ProviderEntrant] = field(default_factory=list)

@dataclass(frozen=True)
class ProviderStream:
    """A broadcast stream configured on a tournament.

    Used to push sets into the provider's public stream queue
    (e.g., start.gg's "On Stream" panel on the bracket page).
    """
    id: str                                # Provider's stream ID
    name: str                              # Display name (e.g., "Main Stage")
    source: Optional[str] = None           # TWITCH / YOUTUBE / etc.
    game: Optional[str] = None             # Optional, only some providers set this


@dataclass(frozen=True)
class ProviderTournament:
    """Top-level tournament metadata."""
    id: str
    name: str
    events: List[ProviderEvent] = field(default_factory=list)
    streams: List[ProviderStream] = field(default_factory=list)

@dataclass(frozen=True)
class ProviderSetResult:
    """Result of a score report or mutation on the provider."""
    success: bool
    set_id: str
    new_state: Optional[ProviderSetState] = None
    error_message: Optional[str] = None
