"""Frozen Hub workflow invariants before provider migration flags are consumed."""
from backend.core.match_state import VALID_TRANSITIONS, WORKFLOW_OVERLAYS, validate_transition


def test_startgg_baseline_workflow_keeps_called_to_live_path():
    assert validate_transition("not_started", "called")
    assert validate_transition("called", "in_progress")
    assert validate_transition("in_progress", "complete")
    assert "conflict" not in VALID_TRANSITIONS.get("called", [])


def test_startgg_baseline_stream_is_a_derived_overlay_not_a_lifecycle_state():
    assert WORKFLOW_OVERLAYS["on_stream"]["derived_from"] == "in_progress"
    assert "on_stream" not in VALID_TRANSITIONS
