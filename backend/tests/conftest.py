import pytest
import os

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Ensure the legacy admin password is set for tests that rely on it."""
    os.environ["HUB_PASSWORD"] = "admin"
