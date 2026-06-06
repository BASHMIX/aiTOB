"""Tests for markSetCalled plumbing (Dual-Mode Check-in, Commit 2).

StartGGProvider.mark_called wraps client.mark_called and reports a ProviderSetResult;
the provider-contract default reports failure so non-start.gg providers degrade gracefully.
"""
import pytest
from unittest.mock import AsyncMock

from backend.core.providers.startgg.provider import StartGGProvider
from backend.core.contracts.tournament_types import ProviderSetState


@pytest.mark.asyncio
async def test_mark_called_success():
    client = AsyncMock()
    client.mark_called = AsyncMock(return_value=True)
    provider = StartGGProvider(client=client)

    result = await provider.mark_called("12345")

    assert result.success is True
    assert result.set_id == "12345"
    assert result.new_state == ProviderSetState.CALLED
    client.mark_called.assert_awaited_once_with("12345")


@pytest.mark.asyncio
async def test_mark_called_failure_surfaces_error():
    client = AsyncMock()
    client.mark_called = AsyncMock(return_value=False)
    provider = StartGGProvider(client=client)

    result = await provider.mark_called("12345")

    assert result.success is False
    assert result.new_state is None
    assert "markSetCalled failed" in (result.error_message or "")


@pytest.mark.asyncio
async def test_mark_called_rejects_preview_set_without_calling_client():
    client = AsyncMock()
    client.mark_called = AsyncMock(return_value=True)
    provider = StartGGProvider(client=client)

    result = await provider.mark_called("preview_999")

    assert result.success is False
    assert "Preview" in (result.error_message or "")
    client.mark_called.assert_not_called()


@pytest.mark.asyncio
async def test_contract_default_mark_called_reports_unsupported():
    """A provider that doesn't override mark_called degrades to a failed result, not a crash."""
    from backend.core.contracts.tournament_provider import ITournamentProvider

    class BareProvider(ITournamentProvider):
        provider_name = "bare"
        async def fetch_tournament(self, s): ...
        async def fetch_sets(self, s): ...
        async def fetch_set_state(self, s): ...
        async def fetch_set_entrant_order(self, s): ...
        async def report_score(self, *a, **k): ...
        async def report_winner_only(self, *a, **k): ...
        async def mark_in_progress(self, s): ...
        async def mark_dq(self, s, w): ...
        async def reset_set(self, s): ...

    result = await BareProvider().mark_called("1")
    assert result.success is False
    assert "does not support" in (result.error_message or "")
