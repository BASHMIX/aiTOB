from backend.core.contracts.tournament_types import ProviderSetState

def map_state(value: object) -> ProviderSetState:
    state = str(value or "pending").lower()
    if state in {"complete", "completed"}: return ProviderSetState.COMPLETE
    # Challonge calls a playable, unreported set "open". It is ready to be
    # called by the Hub, not live on a station yet. Challonge has no remote
    # equivalent of the Hub's local "called" state.
    if state in {"in_progress", "underway"}: return ProviderSetState.IN_PROGRESS
    if state in {"invalid", "cancelled", "canceled", "bye"}: return ProviderSetState.INVALID
    return ProviderSetState.NOT_STARTED
