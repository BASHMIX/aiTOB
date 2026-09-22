from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List
from backend.core.contracts.tournament_types import (
    ProviderTournament, ProviderSet, ProviderSetState, ProviderSetResult,
    ProviderStream,
    ProviderCapabilitiesV2, ProviderCommandResultV2, ProviderCommandV2,
    ProviderSnapshotRequestV2, ProviderSnapshotV2,
)

class ITournamentProvider(ABC):
    """Canonical interface for tournament bracket providers.
    
    Implementations:
      - StartGGProvider  (start.gg GraphQL API)
      - ChallongeProvider (future)
      - ManualProvider   (future — no external API, hub-only)
    
    Design Contracts:
      1. All methods return provider-agnostic dataclasses.
      2. Methods must NOT write to the database or broadcast WebSocket events.
      3. Errors should be raised as exceptions, not returned as None/False.
      4. Implementations must handle their own rate limiting internally.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name, e.g. 'start.gg', 'Challonge'."""
        ...

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Stable machine identifier, such as ``startgg`` or ``challonge``."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilitiesV2:
        """Static adapter capabilities; never performs I/O or exposes secrets."""
        ...

    @abstractmethod
    async def fetch_snapshot(
        self, request: ProviderSnapshotRequestV2
    ) -> ProviderSnapshotV2:
        """Fetch the smallest provider snapshot that satisfies ``request``."""
        ...

    @abstractmethod
    async def execute_remote_command(
        self, command: ProviderCommandV2
    ) -> ProviderCommandResultV2:
        """Execute a command only after the durable command ledger admits it."""
        ...

    # ── Queries ────────────────────────────────────────────────────────

    @abstractmethod
    async def fetch_tournament(self, slug_or_id: str) -> Optional[ProviderTournament]:
        """Fetch tournament metadata including events and entrants.
        
        Args:
            slug_or_id: Provider-specific identifier (slug for start.gg, ID for Challonge)
        
        Returns:
            ProviderTournament or None if not found.
        """
        ...

    @abstractmethod
    async def fetch_sets(self, slug_or_id: str) -> List[ProviderSet]:
        """Fetch all bracket sets for a tournament.
        
        Must handle pagination internally and return the complete list.
        
        Args:
            slug_or_id: Tournament identifier.
        
        Returns:
            List of all sets in provider-agnostic format.
        """
        ...

    @abstractmethod
    async def fetch_set_state(self, set_id: str) -> Optional[ProviderSetState]:
        """Fetch current state of a single set."""
        ...

    @abstractmethod
    async def fetch_set_entrant_order(self, set_id: str) -> List[str]:
        """Fetch the canonical slot ordering of entrants for a set.
        
        Returns:
            List of entrant IDs in slot order [entrant1, entrant2].
        """
        ...

    # ── Mutations ──────────────────────────────────────────────────────

    @abstractmethod
    async def report_score(
        self,
        set_id: str,
        winner_id: str,
        entrant1_id: str,
        entrant2_id: str,
        entrant1_score: int,
        entrant2_score: int,
    ) -> ProviderSetResult:
        """Report match scores with per-game data.
        
        Implementations should handle internal prerequisites 
        (e.g., marking in-progress on start.gg).
        """
        ...

    @abstractmethod
    async def report_winner_only(self, set_id: str, winner_id: str) -> ProviderSetResult:
        """Report only the winner (no score details). Fallback for score report failures."""
        ...

    @abstractmethod
    async def mark_in_progress(self, set_id: str) -> ProviderSetResult:
        """Mark a set as in-progress on the provider."""
        ...

    async def mark_called(self, set_id: str) -> ProviderSetResult:
        """Call a set on the provider (state -> CALLED), triggering its native check-in.

        Optional capability. Providers without a distinct 'called' concept should leave
        this default, which reports failure so callers can fall back (e.g. to a Discord-
        driven check-in). Implementations must not raise.
        """
        return ProviderSetResult(
            success=False, set_id=set_id,
            error_message="Provider does not support calling sets."
        )

    @abstractmethod
    async def mark_dq(self, set_id: str, winner_id: str) -> ProviderSetResult:
        """DQ the opponent and advance the winner."""
        ...

    @abstractmethod
    async def reset_set(self, set_id: str) -> ProviderSetResult:
        """Reset a completed set to its initial state."""
        ...

    async def mark_double_dq(
        self, set_id: str, entrant1_id: str, entrant2_id: str
    ) -> ProviderSetResult:
        """Decline synthetic Double-DQ mutations.

        Provider-native no-show behavior must be observed through snapshots.
        aiTOB never chooses a technical winner merely to close the bracket.
        """
        return ProviderSetResult(
            success=False, set_id=set_id,
            error_message="Double DQ is provider-owned and cannot be synthesized."
        )

    # ── Streams (optional capability) ──────────────────────────────────
    # Providers that don't support streams can return [] from fetch_streams
    # and a failed ProviderSetResult from assign_stream / remove_stream.
    # Callers must treat all three as best-effort and never block on them.

    async def fetch_streams(self, slug_or_id: str) -> List[ProviderStream]:
        """Fetch streams configured on the tournament. Default: no streams."""
        return []

    async def assign_stream(self, set_id: str, stream_id: str) -> ProviderSetResult:
        """Push a set onto the provider's public stream queue. Default: no-op failure."""
        return ProviderSetResult(
            success=False, set_id=set_id,
            error_message="Provider does not support stream queues."
        )

    async def remove_stream(self, set_id: str) -> ProviderSetResult:
        """Remove a set from the provider's public stream queue. Default: no-op failure."""
        return ProviderSetResult(
            success=False, set_id=set_id,
            error_message="Provider does not support stream queues."
        )

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def close(self) -> None:
        """Cleanup resources (HTTP clients, connections). Called on shutdown."""
        pass
