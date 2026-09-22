"""Coordinator-backed, identity-only Challonge resolution service."""
from __future__ import annotations

import time

from backend.core.contracts import ProviderSnapshotRequestV2, ProviderSnapshotV2, SnapshotScope
from backend.core.database import get_fresh_provider_locator_alias
from backend.core.providers.challonge.client import ChallongeRateLimitError
from backend.core.providers.challonge.locator import ChallongeLocator, parse_locator
from backend.core.providers.registry import get_provider_for_account
from backend.core.sync_coordinator import SyncCoordinator


class ChallongeResolutionService:
    def __init__(self, coordinator: SyncCoordinator | None = None) -> None:
        self._coordinator = coordinator or SyncCoordinator()
        # Preview → import commonly happens in one browser session.  Keep only
        # safe, short-lived identity metadata here so it does not spend a second
        # provider request; durable aliases are written only by the import flow.
        self._preview_cache: dict[tuple[str, str], tuple[float, dict]] = {}

    async def resolve(
        self, account_id: str, identifier: str, subdomain: str | None = None, *, workspace_id: str
    ) -> dict:
        locator = parse_locator(identifier, subdomain)
        from backend.core.integrations import get_integration_account
        account_record = await get_integration_account(account_id, workspace_id=workspace_id)
        if not account_record or account_record["provider_type"] != "challonge":
            raise ValueError("An active Challonge integration account is required.")
        account = account_record["id"]
        cached = await get_fresh_provider_locator_alias(
            "challonge", account, locator.subdomain, locator.coordination_key
        )
        if cached:
            return {
                "provider_type": "challonge", "provider_account_id": account,
                "provider_tournament_id": cached["canonical_tournament_id"],
                "name": cached["name"], "subdomain": cached["provider_subdomain"],
                "locator_key": locator.coordination_key, "tournament_slug": cached["tournament_slug"],
                "cached": True,
            }
        preview = self._preview_cache.get((account, locator.coordination_key))
        if preview and preview[0] > time.monotonic():
            return {**preview[1], "cached": True}

        request = ProviderSnapshotRequestV2(
            provider_type="challonge",
            provider_account_id=account,
            tournament_id=locator.coordination_key,
            scope=SnapshotScope.TOURNAMENT_METADATA,
            options={"locator": locator},
        )
        trusted_workspace_id = str(account_record.get("workspace_id") or "")
        if not trusted_workspace_id or trusted_workspace_id != str(workspace_id):
            raise ValueError("Challonge integration account has no workspace owner.")
        provider = await get_provider_for_account("challonge", account, trusted_workspace_id)

        async def operation() -> ProviderSnapshotV2:
            resolved = await provider.resolve(locator.identifier, locator.subdomain)
            return ProviderSnapshotV2(
                request=request,
                payload={"resolved": resolved},
                covered_scopes=frozenset({SnapshotScope.TOURNAMENT_METADATA}),
            )

        try:
            snapshot = await self._coordinator.run_snapshot(request, operation)
        except ChallongeRateLimitError as exc:
            self._coordinator.set_backoff("challonge", account, time.monotonic() + exc.pause_seconds)
            raise
        resolved = dict(snapshot.payload["resolved"])
        self._preview_cache[(account, locator.coordination_key)] = (
            time.monotonic() + 300,
            resolved,
        )
        return resolved


resolution_service = ChallongeResolutionService()
