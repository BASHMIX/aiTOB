from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, FrozenSet, Mapping, Optional, List
from enum import Enum, IntEnum

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
    # Owning event — lets the hub scope matches per game (Tekken 8 vs SF6) so
    # multi-event tournaments don't cross-contaminate the dashboard/dispatch.
    event_id: str = ""
    event_name: str = ""
    # Provider-owned snapshot evidence. Defaults preserve all legacy Start.gg
    # callers while a V2 adapter can keep remote facts separate from Hub state.
    provider_set_id: Optional[str] = None
    provider_state_raw: Optional[str] = None
    provider_revision: Optional[str] = None
    provider_updated_at: Optional[str] = None
    # Result evidence is optional because legacy Start.gg queries did not
    # return it.  Challonge v2.1 verification uses these provider facts rather
    # than inferring a completed result from the local score draft.
    winner_id: Optional[str] = None
    entrant1_score: Optional[int] = None
    entrant2_score: Optional[int] = None

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
    starts_at: Optional[str] = None
    state: Optional[str] = None
    group_stage_enabled: bool = False

@dataclass(frozen=True)
class ProviderSetResult:
    """Result of a score report or mutation on the provider."""
    success: bool
    set_id: str
    new_state: Optional[ProviderSetState] = None
    error_message: Optional[str] = None
    # Safe, structured diagnostics from the adapter.  This is deliberately
    # optional and must never contain credentials or request headers.
    diagnostics: Optional[Mapping[str, Any]] = None


# ── Provider V2 dark-launch contracts ─────────────────────────────────────
# These types deliberately coexist with the legacy ProviderSet/ITournamentProvider
# contract. No runtime consumer imports them until a later feature-flagged phase.


class SnapshotScope(str, Enum):
    TOURNAMENT_METADATA = "tournament_metadata"
    PARTICIPANTS = "participants"
    BRACKET_STRUCTURE = "bracket_structure"
    ACTIVE_MATCHES = "active_matches"
    SINGLE_MATCH = "single_match"
    RESULT_VERIFICATION = "result_verification"
    ADVANCEMENT_NEIGHBORHOOD = "advancement_neighborhood"
    FULL_SNAPSHOT = "full_snapshot"


class SyncCostClass(str, Enum):
    CHEAP = "cheap"
    NORMAL = "normal"
    EXPENSIVE = "expensive"


class ProviderActionKind(str, Enum):
    REMOTE = "remote"
    LOCAL = "local"
    UNAVAILABLE = "unavailable"


class HubStatusV2(str, Enum):
    NOT_STARTED = "not_started"
    AVAILABLE = "available"
    CALLED = "called"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class SyncStatusV2(str, Enum):
    SYNCED = "synced"
    LOCAL_ONLY = "local_only"
    PENDING = "pending"
    ACKNOWLEDGED_UNVERIFIED = "acknowledged_unverified"
    RETRYING = "retrying"
    FAILED = "failed"
    CONFLICT = "conflict"
    NEEDS_REVIEW = "needs_review"


class ProviderCommandState(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    ACKNOWLEDGED = "acknowledged"
    SNAPSHOT_VERIFIED = "snapshot_verified"
    RETRYABLE = "retryable"
    PERMANENT_FAILURE = "permanent_failure"
    CONFLICT = "conflict"
    NEEDS_REVIEW = "needs_review"


class SnapshotPriority(IntEnum):
    """Admission priority only; it never changes provider rate-limit safety."""

    BACKGROUND = 10
    NORMAL = 50
    MANUAL = 80
    PREFLIGHT_MUTATION = 100


class CompletionSourceV2(str, Enum):
    HUB = "hub"
    PROVIDER = "provider"


@dataclass(frozen=True)
class ProviderCapability:
    kind: ProviderActionKind
    reason: Optional[str] = None
    allowed_hub_statuses: FrozenSet[HubStatusV2] = frozenset()


@dataclass(frozen=True)
class ProviderCapabilitiesV2:
    actions: Mapping[str, ProviderCapability] = field(default_factory=dict)
    supports_incremental_sync: bool = False
    supports_conditional_requests: bool = False
    supports_webhooks: bool = False
    supports_targeted_match_fetch: bool = False
    supports_remote_revision: bool = False
    supports_idempotency: bool = False
    minimum_sync_interval_seconds: int = 0

    def for_action(self, action: str) -> ProviderCapability:
        """Return an explicit unavailable projection for undeclared actions."""
        return self.actions.get(
            action,
            ProviderCapability(ProviderActionKind.UNAVAILABLE, "Provider does not declare this action."),
        )


@dataclass(frozen=True)
class ProviderSnapshotRequestV2:
    provider_type: str
    provider_account_id: str
    tournament_id: str
    scope: SnapshotScope
    entity_ids: FrozenSet[str] = frozenset()
    covered_scopes: FrozenSet[SnapshotScope] = frozenset()
    range_key: Optional[str] = None
    covered_range_keys: FrozenSet[str] = frozenset()
    options: Mapping[str, Any] = field(default_factory=dict)
    minimum_revision: Optional[str] = None
    minimum_interval_seconds: int = 0
    priority: SnapshotPriority = SnapshotPriority.NORMAL
    force: bool = False


@dataclass(frozen=True)
class ProviderSnapshotV2:
    request: ProviderSnapshotRequestV2
    payload: Mapping[str, Any]
    revision: Optional[str] = None
    observed_at: Optional[str] = None
    covered_scopes: FrozenSet[SnapshotScope] = frozenset()
    covered_entity_ids: FrozenSet[str] = frozenset()
    covered_range_keys: FrozenSet[str] = frozenset()
    cost_class: SyncCostClass = SyncCostClass.NORMAL


@dataclass(frozen=True)
class ProviderCommandV2:
    command_id: str
    provider_type: str
    provider_account_id: str
    tournament_id: str
    provider_match_id: str
    action: str
    idempotency_key: str
    payload_digest: str
    expected_result: Mapping[str, Any] = field(default_factory=dict)
    precondition_revision: Optional[str] = None


@dataclass(frozen=True)
class ProviderCommandResultV2:
    command_id: str
    state: ProviderCommandState
    acknowledged: bool = False
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ReconciliationDecisionV2:
    decision: str
    reason: str
    sync_status: SyncStatusV2
    match_id: Optional[str] = None


@dataclass(frozen=True)
class MatchCompletionV2:
    """A provider-agnostic completion intent for a later workflow service."""

    match_id: str
    source: CompletionSourceV2
    reason: str
    winner_provider_id: Optional[str] = None
    provider_revision: Optional[str] = None
