"""Provider-specific tournament lifecycle actions.

The Hub owns when an imported tournament is started.  Provider adapters own
the actual mutation so unsupported APIs fail explicitly instead of being
emulated with a local status change.
"""
from __future__ import annotations

from typing import Any, Literal

from backend.core.contracts.tournament_types import ProviderSetResult
from backend.core.provider_commands import DurableProviderMutationService
from backend.core.providers.registry import get_provider_for_tournament

LifecycleAction = Literal["start", "reset"]


async def run_tournament_lifecycle(
    tournament: dict[str, Any], action: LifecycleAction, *, workspace_id: str | None = None
) -> ProviderSetResult:
    provider_type = str(tournament.get("provider_type") or "startgg")
    provider = await get_provider_for_tournament(str(tournament["slug"]), workspace_id)
    reference = str(tournament.get("provider_tournament_id") or tournament["slug"])
    if provider_type == "challonge" and tournament.get("provider_subdomain"):
        reference = f"{reference}@{tournament['provider_subdomain']}"
    # Start.gg models the admin "Reset Bracket" button as a provider-specific
    # event-scoped operation.  Prefer that adapter when available; the legacy
    # tournament-level fallback remains for providers that expose one.
    operation = None
    if action == "reset":
        bracket_method = getattr(provider, "reset_bracket", None)
        if callable(bracket_method):
            operation = lambda: bracket_method(
                reference, event_id=str(tournament.get("event_id") or "") or None
            )
    if operation is None:
        method_name = "start_tournament" if action == "start" else "reset_tournament"
        method = getattr(provider, method_name, None)
        if not callable(method):
            return ProviderSetResult(False, reference, error_message=f"{provider_type} does not expose {action} tournament yet.")
        operation = lambda: method(reference)
    result, command_id = await DurableProviderMutationService(
        workspace_id=str(workspace_id or "")
    ).dispatch_tournament(
        tournament=tournament,
        action=f"tournament_{action}",
        payload={"reference": reference, "event_id": tournament.get("event_id")},
        expected_result={"action": action, "provider_state_changed": True},
        operation=operation,
    )
    diagnostics = dict(result.diagnostics or {})
    diagnostics["provider_command_id"] = command_id
    return ProviderSetResult(
        result.success, result.set_id, result.new_state, result.error_message, diagnostics
    )


__all__ = ["run_tournament_lifecycle"]
