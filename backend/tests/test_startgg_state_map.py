import pytest
from backend.core.providers.startgg.state_map import is_active_state

def test_is_active_state_with_integer():
    assert is_active_state(2) is True
    assert is_active_state(1) is False
    assert is_active_state(3) is False
    assert is_active_state(0) is False
    assert is_active_state(-1) is False

def test_is_active_state_with_string():
    assert is_active_state("ACTIVE") is True
    assert is_active_state("active") is True
    assert is_active_state("  AcTiVe  ") is True
    assert is_active_state("COMPLETED") is False
    assert is_active_state("INACTIVE") is False
    assert is_active_state("") is False
    assert is_active_state("   ") is False

def test_is_active_state_with_invalid_types():
    assert is_active_state(None) is False
    assert is_active_state([]) is False
    assert is_active_state({}) is False
    assert is_active_state(2.0) is False
