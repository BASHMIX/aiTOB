"""Pure reconciliation decisions; this module never performs workflow effects."""
from __future__ import annotations

from backend.core.contracts import ReconciliationDecisionV2, SyncStatusV2


def reconcile_match_snapshot(local: dict, remote: dict, pending_command: dict | None = None) -> ReconciliationDecisionV2:
    """Classify provider facts without changing a station, thread, or match row."""
    if (local.get("p1_entrant_id"), local.get("p2_entrant_id")) != (remote.get("p1_entrant_id"), remote.get("p2_entrant_id")):
        return ReconciliationDecisionV2("INVALIDATE_CALL_FOR_CHANGED_ENTRANTS", "Provider entrants changed", SyncStatusV2.NEEDS_REVIEW)
    raw = str(remote.get("provider_state_raw") or "").lower()
    if raw in {"void", "deleted", "invalid", "cancelled", "canceled"}:
        return ReconciliationDecisionV2("NEEDS_REVIEW", f"Provider returned {raw}", SyncStatusV2.NEEDS_REVIEW)
    if raw == "complete":
        if pending_command:
            expected = pending_command.get("expected_result") or {}
            actual = remote.get("result") or {}
            if expected and actual and expected != actual:
                return ReconciliationDecisionV2("CONFLICT", "Provider result differs from pending command", SyncStatusV2.CONFLICT)
            return ReconciliationDecisionV2("COMPLETE_MATCH_FROM_PROVIDER", "Pending command snapshot verified", SyncStatusV2.SYNCED)
        return ReconciliationDecisionV2("COMPLETE_MATCH_FROM_PROVIDER", "Provider reports completion", SyncStatusV2.SYNCED)
    return ReconciliationDecisionV2("OBSERVE_PROVIDER_STATE", "Non-terminal provider state", SyncStatusV2.SYNCED)
