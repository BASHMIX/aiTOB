import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)

def test_hub_command_requires_auth():
    # POST /api/hub/command without password must fail with 401 Unauthorized
    resp = client.post("/api/hub/command", json={"command": "Who is currently playing?"})
    assert resp.status_code == 401

def test_hub_command_executes_authorized():
    # POST /api/hub/command with password must succeed (returns 200 or maps properly)
    # The endpoint returns a queued status since the Discord bot client might be offline in pytest environment
    resp = client.post(
        "/api/hub/command",
        json={"command": "Who is currently playing?"},
        headers={"X-Hub-Password": "admin"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert "Command queued" in data.get("message") or "Command sent" in data.get("message")

def test_obs_redirection_is_public():
    # GET /obs/{station_id} must redirect (307) and NOT require authentication
    resp = client.get("/obs/station_1", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers.get("location") == "/obs?slot=station_1"

def test_obs_telemetry_is_public():
    # GET /obs/{station_id}/data must return 200 and NOT require authentication
    resp = client.get("/obs/station_1/data")
    assert resp.status_code == 200
    data = resp.json()
    # It might return {"elements": {}, "match": None} if station is missing,
    # or {"station": ..., "active_match": ...} if station is present.
    # The key point is that it returns data without auth.
    assert isinstance(data, dict)
    if "elements" not in data:
        assert "station" in data or "active_match" in data

def test_force_in_progress_requires_auth():
    # POST /active-matches/{id}/force-in-progress without password must fail with 401
    resp = client.post("/api/active-matches/nonexistent_set/force-in-progress")
    assert resp.status_code == 401

def test_force_in_progress_missing_match():
    # With auth, a non-existent set must 404 before any state mutation occurs.
    resp = client.post(
        "/api/active-matches/nonexistent_set/force-in-progress",
        headers={"X-Hub-Password": "admin"},
    )
    assert resp.status_code == 404


def test_resolve_conflict_requires_auth():
    # POST /conflicts/{id}/resolve without password must fail with 401.
    resp = client.post("/api/conflicts/999999/resolve", json={"p1_score": 2, "p2_score": 0})
    assert resp.status_code == 401


def test_resolve_conflict_tied_score_rejected():
    # A tied TO score is rejected with 400 (checked before the conflict lookup).
    resp = client.post(
        "/api/conflicts/999999/resolve",
        json={"p1_score": 1, "p2_score": 1},
        headers={"X-Hub-Password": "admin"},
    )
    assert resp.status_code == 400


def test_resolve_conflict_missing_404():
    # A valid (non-tied) score against a non-existent conflict id must 404.
    resp = client.post(
        "/api/conflicts/999999/resolve",
        json={"p1_score": 2, "p2_score": 0},
        headers={"X-Hub-Password": "admin"},
    )
    assert resp.status_code == 404


def test_double_dq_provider_default_unsupported():
    # The base provider contract advertises double-DQ as unsupported so callers
    # fall back to a local-only resolution. (self is unused in the default body.)
    import asyncio
    from backend.core.contracts.tournament_provider import ITournamentProvider

    result = asyncio.run(ITournamentProvider.mark_double_dq(None, "set1", "e1", "e2"))
    assert result.success is False
    assert "double dq" in (result.error_message or "").lower()
