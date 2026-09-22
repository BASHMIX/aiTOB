"""Workspace/account-scoped provider composition and lifecycle ownership."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.core.contracts import ITournamentProvider


ProviderFactory = Callable[[str], ITournamentProvider]


@dataclass(frozen=True)
class ProviderKey:
    workspace_id: str
    provider_type: str
    account_id: str


class ProviderRegistry:
    """Construct exactly one adapter for each trusted workspace/account binding."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}
        self._instances: dict[ProviderKey, ITournamentProvider] = {}

    def register_factory(self, provider_type: str, factory: ProviderFactory) -> None:
        key = str(provider_type or "").strip().lower()
        if not key:
            raise ValueError("Provider type is required")
        self._factories[key] = factory

    def register_instance(
        self,
        provider_type: str,
        provider: ITournamentProvider,
        *,
        workspace_id: str,
        account_id: str,
    ) -> None:
        key = self._key(provider_type, workspace_id, account_id)
        if provider.provider_type != key.provider_type:
            raise ValueError("Provider instance type does not match its registry key")
        self._instances[key] = provider

    @staticmethod
    def _key(provider_type: str, workspace_id: str, account_id: str) -> ProviderKey:
        values = tuple(str(value or "").strip() for value in (workspace_id, provider_type, account_id))
        if not all(values):
            raise ValueError("Provider resolution requires workspace, provider type, and account")
        workspace, kind, account = values
        return ProviderKey(workspace, kind.lower(), account)

    def resolve(
        self, provider_type: str, *, workspace_id: str, account_id: str
    ) -> ITournamentProvider:
        key = self._key(provider_type, workspace_id, account_id)
        existing = self._instances.get(key)
        if existing is not None:
            return existing
        factory = self._factories.get(key.provider_type)
        if factory is None:
            raise ValueError(f"Unknown provider: {key.provider_type}")
        provider = factory(key.account_id)
        if provider.provider_type != key.provider_type:
            raise ValueError("Provider factory returned the wrong adapter type")
        self._instances[key] = provider
        return provider

    def describe(self, provider_type: str) -> ITournamentProvider:
        """Construct an inert adapter for local capability projection only."""
        kind = str(provider_type or "").strip().lower()
        factory = self._factories.get(kind)
        if factory is None:
            raise ValueError(f"Unknown provider: {kind}")
        return factory("__capability_projection__")

    async def close(self) -> None:
        providers = tuple(self._instances.values())
        self._instances.clear()
        for provider in providers:
            await provider.close()

    def clear_for_tests(self) -> None:
        self._instances.clear()


provider_registry = ProviderRegistry()


def _register_builtin_factories() -> None:
    from backend.core.providers.challonge import ChallongeProvider
    from backend.core.providers.startgg import StartGGProvider

    provider_registry.register_factory(
        "startgg", lambda account_id: StartGGProvider(provider_account_id=account_id)
    )
    provider_registry.register_factory(
        "challonge", lambda account_id: ChallongeProvider(provider_account_id=account_id)
    )


_register_builtin_factories()


async def get_provider_for_account(
    provider_type: str,
    account_id: str,
    workspace_id: str,
) -> ITournamentProvider:
    """Resolve a provider only after verifying the account's tenant ownership."""
    from backend.core.integrations import get_integration_account

    account = await get_integration_account(account_id, workspace_id=workspace_id)
    if not account or str(account.get("provider_type") or "") != provider_type:
        raise ValueError(f"{provider_type} integration account is not available in this workspace")
    if account.get("status") != "active":
        raise ValueError(f"{provider_type} integration account is disabled")
    return provider_registry.resolve(
        provider_type, workspace_id=workspace_id, account_id=account_id
    )


async def get_provider_for_tournament(
    tournament_slug: str, workspace_id: str
) -> ITournamentProvider:
    """Resolve the adapter from one workspace-owned tournament binding."""
    if not str(workspace_id or "").strip():
        raise ValueError("Provider resolution requires a workspace")
    from backend.core.database import get_tournament

    tournament = await get_tournament(tournament_slug, workspace_id)
    if not tournament:
        raise ValueError("Tournament not found")
    trusted_workspace = str(tournament.get("workspace_id") or "")
    if trusted_workspace != str(workspace_id):
        raise ValueError("Tournament workspace binding is invalid")
    provider_type = str(tournament.get("provider_type") or "startgg")
    account_id = str(tournament.get("provider_account_id") or "")
    if not account_id:
        raise ValueError(f"{provider_type} tournament is not bound to an integration account")
    return await get_provider_for_account(provider_type, account_id, trusted_workspace)


def describe_provider(provider_type: str) -> ITournamentProvider:
    return provider_registry.describe(provider_type)


async def shutdown_providers() -> None:
    """Close every account-scoped adapter owned by the registry."""
    await provider_registry.close()
