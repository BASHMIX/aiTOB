"""Avatar storage abstraction: Cloudinary in managed deployments, local only in dev.

store_avatar() normalizes an uploaded image to a square broadcast-quality PNG
(via image_utils.crop_resize_to_png_bytes) and then either uploads it to
Cloudinary or uses the explicitly selected local fallback. Account upload
callers opt into a database data-URL fallback when Cloudinary is unavailable.

PNG is used so transparent (RGBA) avatars are preserved without alpha-channel loss.
Cloudinary credentials are resolved from Hub settings/connections first, then
the CLOUDINARY_URL env var. If none are present (offline dev), we silently use
the local fallback so the flow never breaks.
"""
import os
import asyncio
import base64
from pathlib import Path
from urllib.parse import urlsplit

from backend.core.image_utils import crop_resize_to_png_bytes, save_png_bytes, AVATAR_OUTPUT_SIZE, validate_avatar_quality


_STATIC_ROOT = (Path(__file__).resolve().parents[1] / "api" / "static").resolve()


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


def _cloudinary_public_id(value: str | None) -> str | None:
    """Extract the public id for an avatar uploaded by this module.

    Only Cloudinary's canonical delivery host is accepted. Provider profile
    images are never passed to the destroy API by accident.
    """
    if not value:
        return None
    parsed = urlsplit(str(value))
    if parsed.hostname not in {"res.cloudinary.com", "cloudinary.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    try:
        upload_index = parts.index("upload")
    except ValueError:
        return None
    payload = parts[upload_index + 1 :]
    if payload and payload[0].startswith("v") and payload[0][1:].isdigit():
        payload = payload[1:]
    if not payload:
        return None
    payload[-1] = Path(payload[-1]).stem
    return "/".join(payload) or None


def _local_path(value: str | None) -> Path | None:
    """Resolve only a /static URL inside the API static directory."""
    if not value:
        return None
    parsed = urlsplit(str(value))
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/static/"):
        return None
    candidate = (_STATIC_ROOT / parsed.path.removeprefix("/static/")).resolve()
    if candidate != _STATIC_ROOT and _STATIC_ROOT not in candidate.parents:
        return None
    return candidate


def _destroy_cloudinary(public_id: str, cloudinary_url: str) -> bool:
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
    result = cloudinary.uploader.destroy(
        public_id,
        invalidate=True,
        resource_type="image",
    )
    return str(result.get("result") or "").lower() in {"ok", "not found"}


async def delete_stored_avatar(value: str | None, *, preserve_url: str | None = None) -> bool:
    """Delete one aiTOB avatar after a replacement succeeds.

    Local fallback files are removed directly. Cloudinary assets are destroyed
    through the configured account. URLs that belong to Start.gg or another
    host are intentionally ignored.
    """
    old = str(value or "").strip()
    if not old or (preserve_url and old == str(preserve_url).strip()):
        return False
    if preserve_url and _cloudinary_public_id(old) and _cloudinary_public_id(old) == _cloudinary_public_id(str(preserve_url)):
        # Cloudinary uploads use overwrite=True for the same owner key. A
        # versioned delivery URL may change even though it is the same object;
        # destroying it here would delete the newly uploaded image.
        return False
    local = _local_path(old)
    if local and local.is_file():
        try:
            local.unlink()
            return True
        except OSError:
            return False
    public_id = _cloudinary_public_id(old)
    if not public_id:
        return False
    cloudinary_url = await _resolve_cloudinary_url()
    if not cloudinary_url:
        return False
    try:
        return await asyncio.to_thread(_destroy_cloudinary, public_id, cloudinary_url)
    except Exception as exc:
        # Cleanup must never make a successful replacement fail. The next
        # replacement can retry the destroy operation.
        print(f"[IMG] Could not remove previous Cloudinary avatar: {type(exc).__name__}")
        return False


async def replace_avatar(image_bytes: bytes, public_id: str, previous_urls: list[str | None] | tuple[str | None, ...] = ()) -> str:
    """Store a new avatar and remove old aiTOB copies after it is available."""
    new_url = await store_avatar(image_bytes, public_id)
    seen: set[str] = set()
    for old_url in previous_urls:
        old = str(old_url or "").strip()
        if not old or old in seen or old == new_url:
            continue
        seen.add(old)
        await delete_stored_avatar(old, preserve_url=new_url)
    return new_url


def _database_data_url(png: bytes) -> str:
    """Return a self-contained image value suitable for the DB fallback.

    The media ledger and player override both retain this value, so a failed
    Cloudinary upload does not create an orphaned local file or lose the image.
    """
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


async def store_avatar(image_bytes: bytes, public_id: str, *, fallback_to_database: bool = False) -> str:
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
    if not cloudinary_url:
        if fallback_to_database:
            return _database_data_url(png)
    if storage_mode == "managed" and not cloudinary_url:
        raise RuntimeError("Managed image storage is not configured.")
    if cloudinary_url:
        try:
            return await asyncio.to_thread(_upload_to_cloudinary, png, safe_public_id, cloudinary_url)
        except Exception as exc:
            if fallback_to_database:
                print("[IMG] Cloudinary upload failed; storing the normalized avatar in the database fallback.")
                return _database_data_url(png)
            if storage_mode != "local":
                raise RuntimeError("Managed image storage is unavailable.") from exc
            print("[IMG] Managed image upload failed; using the explicit local development store.")

    return _save_local(png, safe_public_id)
