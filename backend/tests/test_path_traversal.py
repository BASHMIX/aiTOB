import pytest
import os
from backend.api.routers.assets import upload_asset, delete_asset
from backend.api.routers.players import api_upload_avatar
from fastapi import HTTPException
from fastapi import UploadFile

class MockUploadFile(UploadFile):
    def __init__(self, filename):
        self._filename = filename
        self.file = None

    @property
    def filename(self):
        return self._filename

    async def read(self):
        return b"test"

class MockRequest:
    def __init__(self, filename):
        self.filename = filename
    async def form(self):
        return {"avatar": MockUploadFile(self.filename)}

@pytest.mark.asyncio
async def test_assets_upload_traversal():
    res = await upload_asset(file=MockUploadFile("../../../hacked.txt"))
    assert res["name"] == "hacked.txt"
    assert "hacked.txt" in res["url"]
    assert "../" not in res["url"]

@pytest.mark.asyncio
async def test_assets_delete_traversal():
    try:
        await delete_asset("../../../hacked.txt")
    except HTTPException as e:
        assert e.status_code == 404

@pytest.mark.asyncio
async def test_player_avatar_traversal(monkeypatch):
    import backend.api.routers.players as players
    async def mock_save_override(id, data):
        pass
    monkeypatch.setattr(players, "save_player_override", mock_save_override)

    # Test valid image extension with traversal in filename
    req = MockRequest("../../../hacked_avatar.png")
    res = await api_upload_avatar("../../hack", req)
    assert res["avatar_url"] == "/static/avatar_hack.png"

@pytest.mark.asyncio
async def test_player_avatar_extension_validation():
    # Test invalid extension
    req = MockRequest("hacked_avatar.exe")
    with pytest.raises(HTTPException) as excinfo:
        await api_upload_avatar("123", req)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid file extension"
