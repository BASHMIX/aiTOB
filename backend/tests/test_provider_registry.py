import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.core.providers.registry import (
    register_provider,
    get_provider,
    get_provider_for_tournament,
    shutdown_providers,
    _providers
)
from backend.core.contracts import ITournamentProvider

@pytest.fixture(autouse=True)
def reset_providers():
    # Setup
    _providers.clear()
    yield
    # Teardown
    _providers.clear()

def test_register_and_get_provider():
    mock_provider = MagicMock(spec=ITournamentProvider)

    # Test registration
    register_provider("custom", mock_provider)
    assert _providers["custom"] == mock_provider

    # Test retrieval
    retrieved = get_provider("custom")
    assert retrieved == mock_provider

def test_get_provider_lazy_init_startgg():
    # Should create and return StartGGProvider if not in _providers
    provider = get_provider("startgg")
    assert provider is not None
    assert "startgg" in _providers
    assert _providers["startgg"] == provider
    assert provider.__class__.__name__ == "StartGGProvider"

def test_get_provider_unknown_raises_error():
    with pytest.raises(ValueError, match="Unknown provider: unknown. Register it first."):
        get_provider("unknown")

@pytest.mark.asyncio
async def test_get_provider_for_tournament():
    provider = await get_provider_for_tournament("test-slug")
    assert provider is not None
    assert provider.__class__.__name__ == "StartGGProvider"

@pytest.mark.asyncio
async def test_shutdown_providers():
    mock_provider1 = MagicMock(spec=ITournamentProvider)
    mock_provider1.close = AsyncMock()
    mock_provider2 = MagicMock(spec=ITournamentProvider)
    mock_provider2.close = AsyncMock()

    register_provider("p1", mock_provider1)
    register_provider("p2", mock_provider2)

    assert len(_providers) == 2

    await shutdown_providers()

    mock_provider1.close.assert_awaited_once()
    mock_provider2.close.assert_awaited_once()
    assert len(_providers) == 0
