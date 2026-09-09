"""Avatar storage abstraction: Cloudinary in managed deployments, local only in dev.

store_avatar() normalizes an uploaded image to a square broadcast-quality PNG
(via image_utils.crop_resize_to_png_bytes) and then either:
  • uploads it to Cloudinary and returns the public https URL, or
  • saves it under the API static dir only when the explicit local development
    mode is selected.

PNG is used so transparent (RGBA) avatars are preserved without alpha-channel loss.
Cloudinary credentials are resolved from Hub settings/connections first, then
the CLOUDINARY_URL env var. If none are present (offline dev), we silently use
the local fallback so the flow never breaks.
"""
import os
import asyncio

from backend.core.image_utils import crop_resize_to_png_bytes, save_png_bytes, AVATAR_OUTPUT_SIZE, validate_avatar_quality


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


def _upload_to_cloudinary(png_bytes: bytes, public_id: str, cloudinary_url: str) -> str:
    """Blocking Cloudinary upload — call via asyncio.to_thread. Returns secure_url."""
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
    result = cloudinary.uploader.upload(
        png_bytes,
        public_id=public_id,
        folder="aitob/avatars",
        overwrite=True,
        resource_type="image",
        format="png",
    )
    return result["secure_url"]


def _save_local(png_bytes: bytes, public_id: str) -> str:
    """Write the PNG under the static dir; return a /static-relative URL."""
    save_png_bytes(png_bytes, public_id)
    return f"/static/avatars/{public_id}.png"


async def store_avatar(image_bytes: bytes, public_id: str) -> str:
    """Normalize + store an avatar. Returns a renderable URL (Cloudinary) or
    a /static-relative path (local fallback)."""
    valid, reason = validate_avatar_quality(image_bytes)
    if not valid:
        raise ValueError(reason)
    # Do not permit caller-controlled path components in a local fallback.
    safe_public_id = "".join(char for char in str(public_id) if char.isalnum() or char in ("-", "_"))[:120]
    if not safe_public_id:
        raise ValueError("A safe image identifier is required.")
    png = crop_resize_to_png_bytes(image_bytes, AVATAR_OUTPUT_SIZE)

    cloudinary_url = await _resolve_cloudinary_url()
    storage_mode = os.getenv(
        "AITOB_IMAGE_STORAGE_MODE",
        "managed" if os.getenv("AITOB_ENV", "development").lower() == "production" else "local",
    ).lower()
    if storage_mode not in {"managed", "local"}:
        raise RuntimeError("AITOB_IMAGE_STORAGE_MODE must be 'managed' or 'local'.")
    if storage_mode == "managed" and not cloudinary_url:
        raise RuntimeError("Managed image storage is not configured.")
    if cloudinary_url:
        try:
            return await asyncio.to_thread(_upload_to_cloudinary, png, safe_public_id, cloudinary_url)
        except Exception as exc:
            if storage_mode != "local":
                raise RuntimeError("Managed image storage is unavailable.") from exc
            print("[IMG] Managed image upload failed; using the explicit local development store.")

    return _save_local(png, safe_public_id)
