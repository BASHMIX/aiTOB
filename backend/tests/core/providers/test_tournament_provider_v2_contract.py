import inspect

import pytest

from backend.core.contracts import (
    ITournamentProvider,
    ITournamentProviderV2,
    ProviderActionKind,
    ProviderCapabilitiesV2,
    ProviderCapability,
    ProviderCommandResultV2,
    ProviderCommandState,
    ProviderCommandV2,
    ProviderSnapshotRequestV2,
    ProviderSnapshotV2,
    SnapshotScope,
)


class _V2Provider(ITournamentProviderV2):
    @property
    def provider_type(self) -> str:
        return "fixture"

    @property
    def capabilities_v2(self) -> ProviderCapabilitiesV2:
        return ProviderCapabilitiesV2(
            actions={"report_score": ProviderCapability(ProviderActionKind.REMOTE)}
        )

    async def fetch_snapshot_v2(self, request: ProviderSnapshotRequestV2) -> ProviderSnapshotV2:
        return ProviderSnapshotV2(
            request=request, payload={"raw_state": "open"}, revision="revision-1"
        )

    async def execute_remote_command_v2(self, command: ProviderCommandV2) -> ProviderCommandResultV2:
        return ProviderCommandResultV2(command.command_id, ProviderCommandState.ACKNOWLEDGED, True)


def test_v2_contract_exists_alongside_untouched_legacy_contract():
    assert not hasattr(ITournamentProvider, "fetch_snapshot_v2")
    assert inspect.isabstract(ITournamentProviderV2)
    assert _V2Provider().provider_type == "fixture"


@pytest.mark.asyncio
async def test_v2_contract_uses_scoped_snapshot_and_typed_remote_command():
    provider = _V2Provider()
    request = ProviderSnapshotRequestV2(
        provider_type="fixture",
        provider_account_id="account",
        tournament_id="tournament",
        scope=SnapshotScope.SINGLE_MATCH,
        entity_ids=frozenset({"match-1"}),
    )
    snapshot = await provider.fetch_snapshot_v2(request)
    result = await provider.execute_remote_command_v2(
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
    assert provider.capabilities_v2.for_action("mark_called").kind is ProviderActionKind.UNAVAILABLE


def test_v2_architecture_layer_does_not_import_legacy_consumers():
    from backend.core import sync_coordinator

    source = inspect.getsource(sync_coordinator)
    for forbidden in ("StartGGProvider", "ChallongeProvider", "discord", "match_state"):
        assert forbidden not in source


def test_v2_registry_stores_a_factory_without_constructing_an_adapter():
    from backend.core.providers import registry

    created = 0

    def factory() -> ITournamentProviderV2:
        nonlocal created
        created += 1
        return _V2Provider()

    registry.register_provider_v2_factory("fixture-v2", factory)

    assert registry.get_provider_v2_factory("fixture-v2") is factory
    assert created == 0
