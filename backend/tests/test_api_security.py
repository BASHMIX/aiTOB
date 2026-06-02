from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)
import pytest
from backend.api.main import app


def test_sensitive_endpoints_require_auth():
    # Sensitive GET reads must return 401 Unauthorized
    resp = client.get("/api/settings")
    assert resp.status_code == 401
    
    resp = client.get("/api/env")
    assert resp.status_code == 401
    
    resp = client.get("/api/bot-feed")
    assert resp.status_code == 401
    
    resp = client.get("/api/status")
    assert resp.status_code == 401

def test_public_endpoints_no_auth():
    # Public endpoints should not return 401
    resp = client.get("/api/active-matches")
    assert resp.status_code == 200
    
    resp = client.get("/api/conflicts")
    assert resp.status_code == 200
    
    resp = client.get("/health")
    assert resp.status_code == 200

def test_schema_validation_active_match():
    # POST active-matches with missing fields/invalid status must fail validation (422)
    resp = client.post(
        "/api/active-matches",
        json={
            "set_id": "", # empty set_id is disallowed (min_length=1)
            "status": "invalid_status" # invalid enum value
        },
        headers={"Authorization": "Bearer admin"}
    )
    assert resp.status_code == 422

