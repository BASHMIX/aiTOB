import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)

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

def test_cors_headers_restricted():
    # Test an allowed origin
    resp = client.options("/", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Test a disallowed origin
    resp_disallowed = client.options("/", headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"})
    assert resp_disallowed.status_code == 400
    assert "access-control-allow-origin" not in resp_disallowed.headers
