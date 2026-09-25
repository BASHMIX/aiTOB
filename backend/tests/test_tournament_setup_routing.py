"""The live FastAPI application must expose the wizard and edit routes."""
from __future__ import annotations

from backend.api.main import app


def _methods(path: str) -> set[str]:
    return {
        method
        for route in app.routes
        if getattr(route, "path", None) == path
        for method in (getattr(route, "methods", None) or set())
    }


def test_tournament_setup_routes_are_registered_on_the_live_app():
    assert "POST" in _methods("/api/tournament-setup/drafts")
    assert "GET" in _methods("/api/tournament-setup/drafts/{draft_id}")
    assert "POST" in _methods("/api/tournament-setup/tournaments/{tournament_id:path}/edit")


def test_provider_oauth_routes_used_by_the_wizard_are_registered():
    assert "POST" in _methods("/api/auth/providers/{provider}/connect")
    assert "GET" in _methods("/api/auth/providers/{provider}/callback")
