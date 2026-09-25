from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.player_registration import router as registration_router
from backend.api.routers.tournament_setup import router as setup_router
from backend.api.routers.tournaments import router as tournaments_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(setup_router, prefix="/api/tournament-setup")
    app.include_router(registration_router, prefix="/api")
    app.include_router(tournaments_router, prefix="/api/tournaments")
    return TestClient(app)


def _assert_gate(response, code: str) -> None:
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == code


def test_setup_routes_fail_closed_when_wizard_is_disabled(monkeypatch):
    monkeypatch.delenv("TOURNAMENT_SETUP_WIZARD_ENABLED", raising=False)

    _assert_gate(
        _client().post("/api/tournament-setup/drafts"),
        "tournament_setup_wizard_disabled",
    )
    _assert_gate(
        _client().post("/api/tournaments", json={"identifier": "legacy-import"}),
        "tournament_setup_wizard_disabled",
    )


def test_materialize_requires_activation_rollout_gate(monkeypatch):
    monkeypatch.setenv("TOURNAMENT_SETUP_WIZARD_ENABLED", "true")
    monkeypatch.delenv("TOURNAMENT_ACTIVATION_ENABLED", raising=False)

    _assert_gate(
        _client().post("/api/tournament-setup/drafts/draft-1/materialize", json={"revision": 1}),
        "tournament_activation_disabled",
    )


def test_registration_routes_fail_closed_when_registration_is_disabled(monkeypatch):
    monkeypatch.delenv("TOURNAMENT_REGISTRATION_ENABLED", raising=False)

    _assert_gate(
        _client().get("/api/tournaments/tournament-1/registration/config"),
        "tournament_registration_disabled",
    )


def test_provider_start_requires_its_independent_rollout_gate(monkeypatch):
    monkeypatch.setenv("TOURNAMENT_SETUP_WIZARD_ENABLED", "true")
    monkeypatch.delenv("PROVIDER_START_ENABLED", raising=False)

    _assert_gate(
        _client().post("/api/tournament-setup/drafts/draft-1/provider-start", json={"revision": 1}),
        "provider_start_disabled",
    )
