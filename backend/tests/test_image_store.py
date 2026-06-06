"""Tests for the avatar storage abstraction (Cloudinary-or-local)."""
import io
import pytest
from unittest.mock import patch, AsyncMock
from PIL import Image

from backend.core import image_store


def _img_bytes(size=(600, 600)):
    img = Image.new("RGB", size, color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_store_avatar_local_fallback_returns_static_url():
    """With no Cloudinary config, store_avatar saves locally and returns a /static URL."""
    with patch.object(image_store, "_resolve_cloudinary_url", AsyncMock(return_value=None)), \
         patch.object(image_store, "save_png_bytes", return_value="backend/api/static/avatars/abc.png") as mock_save:
        url = await image_store.store_avatar(_img_bytes(), "abc")

    assert url == "/static/avatars/abc.png"
    # The saver receives normalized PNG bytes, not the raw upload.
    assert mock_save.call_count == 1
    saved_bytes, public_id = mock_save.call_args[0]
    assert public_id == "abc"
    assert isinstance(saved_bytes, (bytes, bytearray)) and len(saved_bytes) > 0


@pytest.mark.asyncio
async def test_store_avatar_uses_cloudinary_when_configured():
    """When configured, store_avatar returns the Cloudinary secure URL."""
    cloud_url = "https://res.cloudinary.com/demo/image/upload/aitob/avatars/abc.jpg"
    with patch.object(image_store, "_resolve_cloudinary_url", AsyncMock(return_value="cloudinary://k:s@demo")), \
         patch.object(image_store, "_upload_to_cloudinary", return_value=cloud_url) as mock_up:
        url = await image_store.store_avatar(_img_bytes(), "abc")

    assert url == cloud_url
    assert mock_up.call_count == 1


@pytest.mark.asyncio
async def test_store_avatar_falls_back_when_cloudinary_raises():
    """If the Cloudinary upload throws, we fall back to local save."""
    def _boom(*a, **k):
        raise RuntimeError("network down")

    with patch.object(image_store, "_resolve_cloudinary_url", AsyncMock(return_value="cloudinary://k:s@demo")), \
         patch.object(image_store, "_upload_to_cloudinary", side_effect=_boom), \
         patch.object(image_store, "save_png_bytes", return_value="backend/api/static/avatars/abc.png"):
        url = await image_store.store_avatar(_img_bytes(), "abc")

    assert url == "/static/avatars/abc.png"
