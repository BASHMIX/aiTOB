import pytest
import os
import json
import asyncio
import aiosqlite

from backend.core.match_state import validate_transition, transition_match, VALID_TRANSITIONS
from backend.core.database import init_db, upsert_active_match, get_active_match, get_bot_feed, DB_PATH

# Use a test database path
TEST_DB_PATH = "backend/core/test_database.sqlite"

@pytest.fixture
async def setup_test_db():
    # Override DB_PATH with test db
    import backend.core.database
    import backend.core.match_state
    
    orig_db_path = backend.core.database.DB_PATH
    backend.core.database.DB_PATH = TEST_DB_PATH
    backend.core.match_state.DB_PATH = TEST_DB_PATH
    
    # Initialize the test database
    await init_db()
    
    yield
    
    # Clean up test database
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
            
    # Restore original paths
    backend.core.database.DB_PATH = orig_db_path
    backend.core.match_state.DB_PATH = orig_db_path

def test_workflow_json_exists():
    """Verify that docs/workflows.json exists and contains correct format."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    json_path = os.path.join(root_dir, "docs", "workflows.json")
    
    assert os.path.exists(json_path), f"Workflows file not found at {json_path}"
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert "match_workflow" in data
    assert "states" in data["match_workflow"]
    assert "registration_workflow" in data
    assert "steps" in data["registration_workflow"]

def test_validate_transition(monkeypatch):
    """Test validate_transition function with a mock dictionary."""
    mock_transitions = {
        "state_a": ["state_b", "state_c"],
        "state_b": ["state_d"],
        "state_c": [],
        # state_d is missing from keys
    }
    monkeypatch.setattr("backend.core.match_state.VALID_TRANSITIONS", mock_transitions)

    # Valid transitions
    assert validate_transition("state_a", "state_b") is True
    assert validate_transition("state_a", "state_c") is True
    assert validate_transition("state_b", "state_d") is True

    # Invalid transitions
    assert validate_transition("state_a", "state_d") is False
    assert validate_transition("state_b", "state_c") is False

    # Backwards transition
    assert validate_transition("state_b", "state_a") is False

    # Unknown from_status
    assert validate_transition("unknown_state", "state_b") is False

    # State with no outward transitions
    assert validate_transition("state_c", "state_a") is False
    assert validate_transition("state_c", "any_state") is False

    # Empty strings
    assert validate_transition("", "state_b") is False
    assert validate_transition("state_a", "") is False
    assert validate_transition("", "") is False

    # Missing from keys
    assert validate_transition("state_d", "state_a") is False

def test_transitions_rules():
    """Verify standard transition rules loaded from workflows.json."""
    # Standard path
    assert validate_transition("not_started", "called")
    assert validate_transition("called", "in_progress")
    assert validate_transition("in_progress", "complete")
    
    # Conflict path
    assert validate_transition("in_progress", "conflict")
    assert validate_transition("conflict", "complete")
    
    # Reset path
    assert validate_transition("called", "not_started")
    assert validate_transition("in_progress", "not_started")
    assert validate_transition("complete", "not_started")
    
    # Invalid paths
    assert not validate_transition("not_started", "in_progress")
    assert not validate_transition("not_started", "complete")
    assert not validate_transition("called", "conflict")
    assert not validate_transition("complete", "in_progress")

def test_on_stream_overlay_state():
    """on_stream is documented as an overlay of in_progress but is NOT a transition node."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    json_path = os.path.join(root_dir, "docs", "workflows.json")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    states = data["match_workflow"]["states"]
    assert "on_stream" in states, "on_stream overlay missing from workflows.json"
    on_stream = states["on_stream"]
    assert on_stream.get("overlay") is True
    assert on_stream.get("derived_from") == "in_progress"

    # Overlay states must be excluded from the runtime FSM so transition validation is
    # unchanged — on_stream is a derived view, never a state a match transitions into.
    assert "on_stream" not in VALID_TRANSITIONS
    assert validate_transition("in_progress", "on_stream") is False
    assert set(VALID_TRANSITIONS.keys()) == {
        "not_started", "called", "in_progress", "conflict", "complete"
    }

@pytest.mark.asyncio
async def test_transition_match_function(setup_test_db):
    """Verify transition_match properly transitions states and updates DB."""
    # Seed a match
    set_id = "test_set_123"
    await upsert_active_match(
        set_id=set_id,
        tournament_slug="test-tournament",
        status="not_started",
        p1_name="Player 1",
        p2_name="Player 2"
    )
    
    # Test valid transition
    res = await transition_match(set_id, "called")
    assert res.get("ok") is True
    assert res.get("status") == "called"
    
    match = await get_active_match(set_id)
    assert match["status"] == "called"
    assert match["called_at"] is not None
    
    # Test invalid transition
    res = await transition_match(set_id, "conflict") # called -> conflict is invalid
    assert "error" in res
    
    # Match state should remain unchanged
    match = await get_active_match(set_id)
    assert match["status"] == "called"

@pytest.mark.asyncio
async def test_update_active_match_warning(setup_test_db):
    """Verify that update_active_match logs a warning on invalid transition."""
    # Seed a match
    set_id = "test_set_456"
    await upsert_active_match(
        set_id=set_id,
        tournament_slug="test-tournament",
        status="not_started",
        p1_name="Player 1",
        p2_name="Player 2"
    )
    
    # Perform invalid update directly (not_started -> in_progress)
    from backend.core.database import update_active_match, clear_bot_feed
    await clear_bot_feed()
    
    await update_active_match(set_id, status="in_progress")
    
    # Verify status changed despite being invalid
    match = await get_active_match(set_id)
    assert match["status"] == "in_progress"
    
    # Verify warning logged to bot feed
    feed = await get_bot_feed()
    assert len(feed) > 0
    warning_entry = next((f for f in feed if "Non-standard transition" in f["message"]), None)
    assert warning_entry is not None
    assert warning_entry["level"] == "warn"
    assert "not_started ➔ in_progress" in warning_entry["message"]
