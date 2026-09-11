"""
Unified score reporting — consolidates the try-gameData/fallback-winner-only
pattern used by API, Bot commands, and DM handlers.
"""

from backend.core.contracts import ITournamentProvider, ProviderSetResult
from backend.core.providers.registry import get_provider
from backend.core.provider_feature_flags import get_provider_feature_flags


async def _schedule_post_result_verification(
    set_id: str, provider: ITournamentProvider, workspace_id: str | None = None,
) -> None:
    """Ask the Coordinator for later verification only in its explicit rollout mode.

    This is intentionally provider-neutral. The adapter/sync policy determines
    scope and cost; the legacy flags-off path makes no scheduling change.
    """
    flags = get_provider_feature_flags()
    if not (flags.provider_coordinator_enabled and flags.provider_v2_contracts_enabled):
        return
    try:
        from backend.core.database import get_active_match
        from backend.core.provider_sync_manager import sync_manager
        match = await get_active_match(set_id, workspace_id)
        if match and match.get("tournament_slug"):
            sync_manager.schedule_bracket_sync(
                match["tournament_slug"], workspace_id=match.get("workspace_id") or workspace_id,
            )
    except Exception:
        # Score submission succeeded; deferred UI synchronization is best-effort.
        pass


async def report_score_to_provider(
    set_id: str,
    winner_id: str,
    p1_id: str,
    p2_id: str,
    p1_score: int,
    p2_score: int,
    provider: ITournamentProvider = None,
    workspace_id: str | None = None,
) -> ProviderSetResult:
    """Report scores with automatic fallback to winner-only.
    
    Returns:
        ProviderSetResult — check .success and .error_message
    """
    provider = provider or get_provider()

    # Try full score report
    result = await provider.report_score(
        set_id=set_id,
        winner_id=winner_id,
        entrant1_id=p1_id,
        entrant2_id=p2_id,
        entrant1_score=p1_score,
        entrant2_score=p2_score,
    )
    if result.success:
        await _schedule_post_result_verification(set_id, provider, workspace_id)
        return result

    # Start.gg's report mutation is not safely interchangeable with a
    # winner-only write.  A failed/unknown report must be re-read and surfaced
    # for reconciliation; sending a second mutation could overwrite a result
    # that was accepted before the response was lost.
    if getattr(provider, "provider_type", "") == "startgg":
        return result

    # Fallback: winner-only
    fallback = await provider.report_winner_only(set_id, winner_id)
    if not fallback.success:
        return ProviderSetResult(
            success=False,
            set_id=set_id,
            error_message=f"Full report failed: {result.error_message}; "
                          f"Winner-only fallback also failed: {fallback.error_message}"
        )
    await _schedule_post_result_verification(set_id, provider, workspace_id)
    return fallback
