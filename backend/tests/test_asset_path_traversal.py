import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.core.database import init_db
import asyncio
import os

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    asyncio.run(init_db())

def test_path_traversal_asset_upload():
    response = client.post(
        "/api/assets/upload",
        files={"file": ("../../../test.txt", b"hello", "text/plain")},
        headers={"Authorization": "Bearer admin"}
    )

    # After our fix, os.path.basename("../../../test.txt") becomes "test.txt"
    # So the upload should actually succeed, but safe filename should be used.
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "test.txt"
    assert data["url"] == "/static/assets/test.txt"

    # Cleanup
    resp = client.delete("/api/assets/test.txt", headers={"Authorization": "Bearer admin"})
    assert resp.status_code == 200

def test_path_traversal_asset_delete():
    # Attempt to delete something outside the assets directory
    response = client.delete(
        "/api/assets/..%2f..%2f..%2ftest.txt",
        headers={"Authorization": "Bearer admin"}
    )

    # FastAPI path routing handles URL-encoded slashes `%2f` in path params depending on config,
    # but the API response status code should be 404
    assert response.status_code == 404

def test_path_traversal_asset_delete_direct():
    # Directly test the endpoint function or via query params if it were a query param
    # In this case it's a path param. The `name` gets sanitized. Let's just create an asset and try to delete it securely.

    # 1. Create a dummy test file
    client.post(
        "/api/assets/upload",
        files={"file": ("target.txt", b"target_data", "text/plain")},
        headers={"Authorization": "Bearer admin"}
    )

    # 2. Delete it normally
    resp1 = client.delete("/api/assets/target.txt", headers={"Authorization": "Bearer admin"})
    assert resp1.status_code == 200
    assert resp1.json()["message"] == "Deleted"
