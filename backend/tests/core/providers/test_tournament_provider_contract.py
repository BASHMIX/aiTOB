import inspect

import pytest

from backend.core.contracts import (
    ITournamentProvider,
    ProviderActionKind,
    ProviderCapabilitiesV2,
    ProviderCapability,
    ProviderCommandResultV2,
    ProviderCommandState,
    ProviderCommandV2,
    ProviderSetResult,
    ProviderSnapshotRequestV2,
    ProviderSnapshotV2,
    SnapshotScope,
)
from backend.core.providers.registry import ProviderRegistry


class _CanonicalProvider(ITournamentProvider):
    @property
    def provider_name(self) -> str:
        return "Fixture"

    @property
    def provider_type(self) -> str:
        return "fixture"

    @property
    def capabilities(self) -> ProviderCapabilitiesV2:
        return ProviderCapabilitiesV2(
            actions={"report_score": ProviderCapability(ProviderActionKind.REMOTE)}
        )

    async def fetch_snapshot(self, request: ProviderSnapshotRequestV2) -> ProviderSnapshotV2:
        return ProviderSnapshotV2(
            request=request, payload={"raw_state": "open"}, revision="revision-1"
        )

    async def execute_remote_command(self, command: ProviderCommandV2) -> ProviderCommandResultV2:
        return ProviderCommandResultV2(
            command.command_id, ProviderCommandState.ACKNOWLEDGED, True
        )

    async def fetch_tournament(self, slug_or_id):
        return None

    async def fetch_sets(self, slug_or_id):
        return []

    async def fetch_set_state(self, set_id):
        return None

    async def fetch_set_entrant_order(self, set_id):
        return []

    async def report_score(self, set_id, winner_id, entrant1_id, entrant2_id,
                           entrant1_score, entrant2_score):
        return ProviderSetResult(True, set_id)

    async def report_winner_only(self, set_id, winner_id):
        return ProviderSetResult(True, set_id)

    async def mark_in_progress(self, set_id):
        return ProviderSetResult(True, set_id)

    async def mark_dq(self, set_id, winner_id):
        return ProviderSetResult(True, set_id)

    async def reset_set(self, set_id):
        return ProviderSetResult(True, set_id)


def test_one_canonical_contract_contains_reads_and_commands():
    assert inspect.isabstract(ITournamentProvider)
    assert _CanonicalProvider().provider_type == "fixture"
    assert hasattr(ITournamentProvider, "fetch_snapshot")
    assert hasattr(ITournamentProvider, "execute_remote_command")


@pytest.mark.asyncio
async def test_canonical_contract_uses_scoped_snapshot_and_typed_remote_command():
    provider = _CanonicalProvider()
    request = ProviderSnapshotRequestV2(
        provider_type="fixture",
        provider_account_id="account",
        tournament_id="tournament",
        scope=SnapshotScope.SINGLE_MATCH,
        entity_ids=frozenset({"match-1"}),
    )
    snapshot = await provider.fetch_snapshot(request)
    result = await provider.execute_remote_command(
        ProviderCommandV2(
            command_id="command-1", provider_type="fixture", provider_account_id="account",
            tournament_id="tournament", provider_match_id="match-1", action="report_score",
            idempotency_key="key-1", payload_digest="digest",
        )
    )

    assert snapshot.request.scope is SnapshotScope.SINGLE_MATCH
    assert snapshot.payload["raw_state"] == "open"
    assert snapshot.revision == "revision-1"
    assert result.state is ProviderCommandState.ACKNOWLEDGED
    assert result.acknowledged is True
    assert provider.capabilities.for_action("mark_called").kind is ProviderActionKind.UNAVAILABLE


def test_coordinator_architecture_does_not_import_provider_adapters():
    from backend.core import sync_coordinator

    source = inspect.getsource(sync_coordinator)
    for forbidden in ("StartGGProvider", "ChallongeProvider", "discord", "match_state"):
        assert forbidden not in source


def test_account_scoped_registry_factory_is_lazy_and_cached_per_binding():
    registry = ProviderRegistry()
    created = 0

    def factory(_account_id: str) -> ITournamentProvider:
        nonlocal created
        created += 1
        return _CanonicalProvider()

    registry.register_factory("fixture", factory)
    assert created == 0
    first = registry.resolve("fixture", workspace_id="workspace-a", account_id="account-a")
    second = registry.resolve("fixture", workspace_id="workspace-a", account_id="account-a")
    third = registry.resolve("fixture", workspace_id="workspace-a", account_id="account-b")

    assert first is second
    assert third is not first
    assert created == 2
