"""
Unified score reporting — consolidates the try-gameData/fallback-winner-only
pattern used by API, Bot commands, and DM handlers.
"""

from backend.core.contracts import ITournamentProvider, ProviderSetResult
from backend.core.providers.registry import get_provider


async def report_score_to_provider(
    set_id: str,
    winner_id: str,
    p1_id: str,
    p2_id: str,
    p1_score: int,
    p2_score: int,
    provider: ITournamentProvider = None,
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
    return fallback
