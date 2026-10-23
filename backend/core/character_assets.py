"""Character asset management and Cloudinary mirroring for aiTOB."""

import os
import re
import asyncio
from typing import Any
import cloudinary
import cloudinary.uploader
from backend.core.image_store import _resolve_cloudinary_url

def slugify_character_name(name: str) -> str:
    """Normalize character name into a clean, filesystem/URL safe slug.
    Examples:
      'A.K.I.' -> 'aki'
      'Chun-Li' -> 'chun_li'
      'Dee Jay' -> 'dee_jay'
      'E. Honda' -> 'e_honda'
      'M. Bison' -> 'm_bison'
      'Marisa' -> 'marisa'
    """
    cleaned = (name or "").strip().lower()
    cleaned = cleaned.replace(".", "").replace("'", "")
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    return cleaned.strip("_") or "character"


def _upload_single_character(
    source_url: str,
    folder: str,
    public_id: str,
    cloudinary_url: str,
) -> str | None:
    """Upload one remote character image to Cloudinary."""
    try:
        cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
        res = cloudinary.uploader.upload(
            source_url,
            public_id=public_id,
            folder=folder,
            overwrite=True,
            resource_type="image",
            format="png",
        )
        return res.get("secure_url")
    except Exception as exc:
        print(f"[CHAR_ASSETS] Error uploading {public_id} to Cloudinary: {exc}")
        return None


async def mirror_characters_to_cloudinary(
    game_slug: str,
    characters: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Mirror all character images from a provider catalog into Cloudinary CDN.
    Returns (updated_characters_list, uploaded_count).
    """
    cloudinary_url = await _resolve_cloudinary_url()
    if not cloudinary_url:
        print("[CHAR_ASSETS] Cloudinary URL not configured; skipping mirror.")
        return characters, 0

    normalized_game = slugify_character_name(game_slug or "general")
    folder = f"aitob/characters/{normalized_game}"

    updated: list[dict[str, Any]] = []
    upload_tasks = []

    for char in characters:
        char_copy = dict(char)
        img_url = char_copy.get("image_url") or (char_copy.get("images", [{}])[0].get("url") if char_copy.get("images") else None)
        char_name = char_copy.get("name", "unknown")
        char_slug = slugify_character_name(char_name)
        char_copy["character_slug"] = char_slug

        # If already mirrored to our Cloudinary, skip re-upload
        if img_url and "res.cloudinary.com" in img_url and folder in img_url:
            char_copy["image_url"] = img_url
            char_copy["cloudinary_url"] = img_url
            updated.append((char_copy, None))
            continue

        if img_url and img_url.startswith("http"):
            char_copy["original_image_url"] = img_url
            # Queue async upload
            task = asyncio.to_thread(_upload_single_character, img_url, folder, char_slug, cloudinary_url)
            upload_tasks.append((len(updated), task))
            updated.append((char_copy, None))
        else:
            updated.append((char_copy, None))

    # Run uploads concurrently in batches
    uploaded_count = 0
    if upload_tasks:
        results = await asyncio.gather(*(t[1] for t in upload_tasks), return_exceptions=True)
        for (idx, _), result in zip(upload_tasks, results):
            if isinstance(result, str) and result.startswith("http"):
                updated[idx][0]["image_url"] = result
                updated[idx][0]["cloudinary_url"] = result
                uploaded_count += 1

    return [item[0] for item in updated], uploaded_count
