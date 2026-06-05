"""Avatar storage abstraction: Cloudinary when configured, local-disk fallback.

store_avatar() normalizes an uploaded image to a square broadcast-quality JPEG
(via image_utils.crop_resize_to_jpeg_bytes) and then either:
  • uploads it to Cloudinary and returns the public https URL, or
  • saves it under the API static dir and returns a /static-relative URL the
    Hub dashboard and OBS overlay can render directly.

Cloudinary credentials are resolved from Hub settings/connections first, then
the CLOUDINARY_URL env var. If none are present (offline dev), we silently use
the local fallback so the flow never breaks.
"""
import os
import asyncio

from backend.core.image_utils import crop_resize_to_jpeg_bytes, save_jpeg_bytes, AVATAR_OUTPUT_SIZE


async def _resolve_cloudinary_url() -> str | None:
    """Return the configured Cloudinary URL (cloudinary://key:secret@cloud) or None.

    Settings/connections (set via Hub UI) take precedence over the env var.
    """
    try:
        from backend.core.database import get_setting, get_connection
        return (
            await get_setting("CLOUDINARY_URL")
            or await get_connection("CLOUDINARY_URL")
            or os.getenv("CLOUDINARY_URL")
        )
    except Exception:
        return os.getenv("CLOUDINARY_URL")


def _upload_to_cloudinary(jpeg_bytes: bytes, public_id: str, cloudinary_url: str) -> str:
    """Blocking Cloudinary upload — call via asyncio.to_thread. Returns secure_url."""
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
    result = cloudinary.uploader.upload(
        jpeg_bytes,
        public_id=public_id,
        folder="aitob/avatars",
        overwrite=True,
        resource_type="image",
    )
    return result["secure_url"]


def _save_local(jpeg_bytes: bytes, public_id: str) -> str:
    """Write the JPEG under the static dir; return a /static-relative URL."""
    save_jpeg_bytes(jpeg_bytes, public_id)
    return f"/static/avatars/{public_id}.jpg"


async def store_avatar(image_bytes: bytes, public_id: str) -> str:
    """Normalize + store an avatar. Returns a renderable URL (Cloudinary) or
    a /static-relative path (local fallback)."""
    jpeg = crop_resize_to_jpeg_bytes(image_bytes, AVATAR_OUTPUT_SIZE)

    cloudinary_url = await _resolve_cloudinary_url()
    if cloudinary_url:
        try:
            return await asyncio.to_thread(_upload_to_cloudinary, jpeg, public_id, cloudinary_url)
        except Exception as e:
            print(f"[IMG] Cloudinary upload failed ({e}); falling back to local save.")

    return _save_local(jpeg, public_id)
