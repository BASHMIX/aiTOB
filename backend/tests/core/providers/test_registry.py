import pytest
from unittest.mock import Mock, AsyncMock

from backend.core.contracts import ITournamentProvider
from backend.core.providers.registry import (
    register_provider,
    get_provider,
    get_provider_for_tournament,
    shutdown_providers,
    _providers
)
from backend.core.providers.startgg import StartGGProvider


class MockProvider(ITournamentProvider):
    @property
    def provider_name(self) -> str:
        return "mock_provider"

    async def fetch_tournament(self, slug_or_id: str): pass
    async def fetch_sets(self, slug_or_id: str): pass
    async def fetch_set_state(self, set_id: str): pass
    async def fetch_set_entrant_order(self, set_id: str): pass
    async def report_score(self, set_id, winner_id, e1_id, e2_id, e1_score, e2_score): pass
    async def report_winner_only(self, set_id, winner_id): pass
    async def mark_in_progress(self, set_id): pass
    async def mark_dq(self, set_id, winner_id): pass
    async def reset_set(self, set_id): pass
    async def close(self): pass


@pytest.fixture(autouse=True)
def clear_registry():
    """Ensure the registry is clear before and after each test."""
    _providers.clear()
    yield
    _providers.clear()


def test_get_provider_lazy_init_startgg():
    assert "startgg" not in _providers
    provider = get_provider("startgg")
    assert isinstance(provider, StartGGProvider)
    assert "startgg" in _providers
    assert _providers["startgg"] is provider


def test_get_provider_unknown_raises_error():
    with pytest.raises(ValueError, match="Unknown provider: custom. Register it first."):
        get_provider("custom")


def test_register_and_get_custom_provider():
    mock_provider = MockProvider()
    register_provider("custom", mock_provider)

    assert "custom" in _providers
    provider = get_provider("custom")
    assert provider is mock_provider


def test_get_provider_returns_same_instance():
    provider1 = get_provider("startgg")
    provider2 = get_provider("startgg")

    assert provider1 is provider2
    assert isinstance(provider1, StartGGProvider)


@pytest.mark.asyncio
async def test_get_provider_for_tournament():
    provider = await get_provider_for_tournament("any_slug")
    assert isinstance(provider, StartGGProvider)
    assert _providers["startgg"] is provider


@pytest.mark.asyncio
async def test_shutdown_providers():
    mock_provider = MockProvider()
    mock_provider.close = AsyncMock()

    register_provider("mock", mock_provider)
    assert len(_providers) == 1

    await shutdown_providers()

    mock_provider.close.assert_awaited_once()
    assert len(_providers) == 0
