import pytest
import re
from backend.core.match_state import generate_lobby_password

def test_generate_lobby_password():
    """Verify that generate_lobby_password returns a 4-digit string."""
    for _ in range(100):
        password = generate_lobby_password()

        # Must be a string
        assert isinstance(password, str)

        # Must be exactly 4 characters long
        assert len(password) == 4

        # Must contain only digits
        assert password.isdigit()

        # Optional: check if it falls within the 1000-9999 range logically
        assert 1000 <= int(password) <= 9999
