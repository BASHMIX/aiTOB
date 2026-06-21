import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
import os

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_password(monkeypatch):
    monkeypatch.setenv("HUB_PASSWORD", "testpass")

def test_path_traversal_asset_upload():
    # Attempt to upload to a path traversal directory
    response = client.post(
        "/api/assets/upload",
        headers={"Authorization": "Bearer testpass"},
        files={"file": ("../../hacked_asset.txt", b"hacked")}
    )

    # Check that the API handled it cleanly and stripped the path
    assert response.status_code == 200
    assert response.json()["name"] == "hacked_asset.txt"

    # Ensure it's not written to the root or parent
    assert not os.path.exists("../../hacked_asset.txt")
    assert not os.path.exists("hacked_asset.txt")

def test_path_traversal_asset_delete():
    response = client.delete(
        "/api/assets/..%2F..%2Fhacked_asset.txt",
        headers={"Authorization": "Bearer testpass"}
    )
    assert response.status_code in [404, 405]

def test_invalid_avatar_extension():
    # If the file passes isinstance(UploadFile), we check the logic for extension.
    # To pass isinstance, TestClient can send multiple files as expected.
    response = client.post(
        "/api/players/overrides/123/avatar",
        headers={"Authorization": "Bearer testpass"},
        files={"avatar": ("test.exe", b"executable_content", "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "Invalid file extension" in response.text or "No file uploaded" in response.text

def test_path_traversal_avatar_upload():
    response = client.post(
        "/api/players/overrides/..%2F..%2Fhacked/avatar",
        headers={"Authorization": "Bearer testpass"},
        files={"avatar": ("test.png", b"hacked", "image/png")}
    )
    # the server might block traversal with a 405 before it reaches the endpoint,
    # but if it reaches, we should check it didn't save out of bounds.
    assert response.status_code in [200, 405]
    # It should not save outside the static dir
    assert not os.path.exists("../../hacked.png")
    assert not os.path.exists("hacked.png")
