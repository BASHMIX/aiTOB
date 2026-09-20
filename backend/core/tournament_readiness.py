"""Server-owned readiness projection for setup drafts."""
from __future__ import annotations

from typing import Any

from backend.core.tournament_setup import get_draft
from backend.core.provider_discovery import freshness_seconds


async def compute_readiness(draft_id: str, workspace_id: str, *, purpose: str = "draft_review") -> dict[str, Any]:
    draft = await get_draft(draft_id, workspace_id)
    checks: list[dict[str, Any]] = []
    provider = draft.get("provider_scope") or {}
    if not provider or not provider.get("selected_scope"):
        checks.append({"code": "provider_scope_required", "step": "provider", "field_path": "provider_scope", "requirement": "required", "state": "blocked", "message": "Select an exact provider Event or bracket.", "retryable": False})
    else:
        observed = provider.get("observed_at") or provider.get("provider_observed_at")
        age = freshness_seconds(observed) if observed else 0
        if observed and age > 900:
            checks.append({"code": "provider_scope_stale", "step": "provider", "field_path": "provider_scope", "requirement": "required", "state": "blocked", "message": "Provider scope preview is stale; recheck the selected Event or bracket.", "remediation": "provider.recheck", "retryable": True})
        else:
            checks.append({"code": "provider_scope_ready", "step": "provider", "field_path": "provider_scope", "requirement": "required", "state": "ready", "message": "Provider scope selected.", "retryable": False})
    review = draft.get("tournament_review") or {}
    if not (review.get("display_name") or provider.get("tournament", {}).get("name")):
        checks.append({"code": "tournament_name_required", "step": "tournament", "field_path": "display_name", "requirement": "required", "state": "blocked", "message": "Add a tournament name.", "retryable": False})
    else:
        checks.append({"code": "tournament_name_ready", "step": "tournament", "field_path": "display_name", "requirement": "required", "state": "ready", "message": "Tournament identity is ready.", "retryable": False})
    discord = draft.get("discord_setup") or {}
    checks.append({"code": "discord_optional", "step": "discord", "requirement": "optional", "state": "ready" if not discord.get("enabled") else ("ready" if discord.get("guild_id") else "blocked"), "message": "Discord setup is optional." if not discord.get("enabled") else "Select a permitted Discord server.", "retryable": False})
    assistant = draft.get("assistant_setup") or {}
    checks.append({"code": "assistant_optional", "step": "assistant", "requirement": "optional", "state": "ready", "message": "AI assistant may be configured later.", "retryable": False})
    required = [check for check in checks if check["requirement"] == "required"]
    state = "blocked" if any(check["state"] == "blocked" for check in required) else ("warning" if any(check["state"] == "warning" for check in checks) else "ready")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for check in checks:
        grouped.setdefault(check["step"], []).append(check)
    return {"draft_id": draft_id, "revision": draft["revision"], "purpose": purpose, "state": state, "checks": checks, "by_step": grouped}


get_tournament_readiness = compute_readiness

__all__ = ["compute_readiness", "get_tournament_readiness"]
