import pytest
from unittest.mock import patch
from backend.api.routers.assets import upload_asset, delete_asset
from backend.api.routers.players import api_upload_avatar
from fastapi import UploadFile, Request
from starlette.datastructures import FormData, Headers
import io
import os

class MockUploadFile(UploadFile):
    def __init__(self, filename: str, content: bytes):
        super().__init__(file=io.BytesIO(content), size=len(content), filename=filename)

@pytest.mark.asyncio
async def test_upload_asset_path_traversal(tmp_path):
    with patch("backend.api.routers.assets.ASSETS_DIR", str(tmp_path)):
        file = MockUploadFile(filename="../../../evil.txt", content=b"evil")
        res = await upload_asset(file)
        assert res["name"] == "evil.txt"
        assert "evil.txt" in res["url"]

        # Verify it was saved safely in tmp_path
        assert os.path.exists(os.path.join(str(tmp_path), "evil.txt"))

@pytest.mark.asyncio
async def test_delete_asset_path_traversal(tmp_path):
    with patch("backend.api.routers.assets.ASSETS_DIR", str(tmp_path)):
        dummy_path = os.path.join(str(tmp_path), "dummy_test.txt")
        with open(dummy_path, "wb") as f:
            f.write(b"test")

        res = await delete_asset("../../../dummy_test.txt")
        assert res["message"] == "Deleted"
        assert not os.path.exists(dummy_path)


class MockRequest(Request):
    def __init__(self, filename: str, content: bytes):
        self._filename = filename
        self._content = content

    async def form(self):
        headers = Headers({"content-type": "image/png"})
        file = UploadFile(filename=self._filename, file=io.BytesIO(self._content), headers=headers)
        return FormData([("avatar", file)])


@pytest.mark.asyncio
async def test_api_upload_avatar_path_traversal(tmp_path):
    # Mock save_player_override and the static directory
    with patch("backend.api.routers.players.save_player_override"), \
         patch("backend.api.routers.players.os.path.dirname", return_value=str(tmp_path)):

        req = MockRequest(filename="something.png/../../../evil.txt", content=b"evil")
        res = await api_upload_avatar("test_traversal_id", req)

        assert res["avatar_url"].startswith("/static/avatar_test_traversal_id.txt") == False
        assert res["avatar_url"].endswith(".png")
        assert "avatar_test_traversal_id.png" in res["avatar_url"]
