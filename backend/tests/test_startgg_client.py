import pytest
from backend.core.providers.startgg import client as startgg_client
from backend.core.providers.startgg.client import get_client, StartGGClient

@pytest.fixture(autouse=True)
def reset_client_instance():
    """Reset the singleton instance before and after each test."""
    # Store original state
    original_instance = startgg_client._client_instance
    startgg_client._client_instance = None

    yield

    # Restore original state
    startgg_client._client_instance = original_instance

def test_get_client_returns_instance():
    """Test that get_client returns a StartGGClient instance."""
    client = get_client()
    assert isinstance(client, StartGGClient)

def test_get_client_is_singleton():
    """Test that multiple calls to get_client return the same instance."""
    client1 = get_client()
    client2 = get_client()
    assert client1 is client2

def test_get_client_creates_new_instance_when_reset():
    """Test that if the internal instance is None, a new one is created."""
    client1 = get_client()

    # Reset the singleton
    startgg_client._client_instance = None

    client2 = get_client()
    assert client1 is not client2
    assert isinstance(client2, StartGGClient)
