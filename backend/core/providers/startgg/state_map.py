"""
Mapping from Start.gg ActivityState integers to provider-agnostic states.
Moved from database.py to keep provider-specific knowledge isolated.
"""

from backend.core.contracts.tournament_types import ProviderSetState

# Start.gg ActivityState → ProviderSetState
SGG_STATE_MAP: dict[int, ProviderSetState] = {
    1: ProviderSetState.NOT_STARTED,   # CREATED
    2: ProviderSetState.IN_PROGRESS,   # ACTIVE
    3: ProviderSetState.COMPLETE,      # COMPLETED
    4: ProviderSetState.NOT_STARTED,   # READY (reset)
    5: ProviderSetState.INVALID,       # INVALID (bye)
    6: ProviderSetState.CALLED,        # CALLED
    7: ProviderSetState.QUEUED,        # QUEUED
}

# States that represent terminal results on the provider
SGG_TERMINAL_STATES: set[int] = {3}

# States that should auto-add matches to the hub
SGG_AUTO_ADD_STATES: set[int] = {1, 2, 6, 7}


def is_active_state(state) -> bool:
    """True iff a start.gg ActivityState value means ACTIVE (in progress).

    start.gg's GraphQL API returns this field as int for `Tournament.state`
    but as the enum-name string (e.g. "ACTIVE") for `Event.state` and
    `Phase.state`. Always go through this helper instead of `state == 2`.
    """
    if isinstance(state, int):
        return state == 2
    if isinstance(state, str):
        return state.strip().upper() == "ACTIVE"
    return False
