"""Deterministic player-image validation used by registration.

Registration never invokes an AI safety provider.  The service only decodes,
normalizes and applies explicit size/dimension/type limits; the organizer then
chooses keep, replace or skip.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True, slots=True)
class ImageValidation:
    ok: bool
    reason_code: str
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    normalized_bytes: bytes | None = None


ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024
MAX_DIMENSION = 8192
MAX_PIXELS = 32_000_000


def validate_player_image(data: bytes, *, mime_type: str | None = None) -> ImageValidation:
    if not isinstance(data, (bytes, bytearray)) or not data:
        return ImageValidation(False, "empty_file")
    if len(data) > MAX_BYTES:
        return ImageValidation(False, "file_too_large")
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            actual = Image.MIME.get(image.format)
            image.load()
            if width <= 0 or height <= 0 or width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
                return ImageValidation(False, "dimensions_unsupported", actual, width, height)
            if mime_type and mime_type.lower() not in ALLOWED_MIME:
                return ImageValidation(False, "mime_unsupported", actual, width, height)
            if actual not in ALLOWED_MIME:
                return ImageValidation(False, "type_unsupported", actual, width, height)
            # Normalize to a deterministic PNG, preserving alpha where present.
            normalized = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = BytesIO()
            normalized.save(output, format="PNG", optimize=True)
            return ImageValidation(True, "ok", actual, width, height, output.getvalue())
    except (UnidentifiedImageError, OSError, ValueError):
        return ImageValidation(False, "decode_failed")


def apply_image_policy(policy: Literal["disabled", "optional", "required"], validation: ImageValidation, *, has_existing: bool = False) -> str:
    if policy == "disabled":
        return "skip"
    if validation.ok:
        return "replace"
    if policy == "optional" and has_existing:
        return "keep"
    return "needs_review"


__all__ = ["ImageValidation", "validate_player_image", "apply_image_policy"]
