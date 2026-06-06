from PIL import Image
from io import BytesIO
import os
import google.generativeai as genai

# Broadcast avatars must be high enough resolution to render cleanly on stream
# overlays. 500x500 is the minimum we accept (start.gg profile pics are often
# smaller, which is exactly why we collect our own).
MIN_AVATAR_DIM = 500
MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_ASPECT_RATIO = 3.0
AVATAR_OUTPUT_SIZE = 512


def validate_avatar_quality(image_bytes: bytes) -> tuple[bool, str]:
    """Validate an uploaded avatar, returning (ok, specific_reason).

    Each failure path returns a precise, user-facing explanation of EXACTLY
    why the image was rejected — never a silent/generic failure.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
    except Exception as e:
        return False, f"Invalid image file — I couldn't read that as an image ({e})."

    if width < MIN_AVATAR_DIM or height < MIN_AVATAR_DIM:
        return False, (
            f"Image resolution is too low ({width}x{height}). Broadcast avatars must be at "
            f"least {MIN_AVATAR_DIM}x{MIN_AVATAR_DIM}px — please upload a larger, higher-quality image."
        )

    if len(image_bytes) > MAX_AVATAR_BYTES:
        return False, "File size is too large (max 5MB). Please upload a smaller file."

    ratio = max(width, height) / min(width, height)
    if ratio > MAX_ASPECT_RATIO:
        return False, (
            f"The image is too narrow or too wide ({width}x{height}). Please provide a more "
            "square photo (aspect ratio under 3:1)."
        )

    return True, "OK"

async def validate_avatar_safety(image_bytes: bytes) -> tuple[bool, str]:
    """
    Uses Gemini to check if the image contains offensive or inappropriate content.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return True, "Safety check skipped (no API key)"
        
    genai.configure(api_key=api_key)
    # 'gemini-1.5-flash' 404s on the current v1beta API. Default to the model the
    # rest of the codebase uses (gemini-2.5-flash); override via GEMINI_VISION_MODEL.
    model_name = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
    model = genai.GenerativeModel(model_name)
    
    try:
        prompt = "Analyze this image for a tournament profile. Is it offensive, inappropriate, or harmful? Respond with 'SAFE' or a short reason why it is not safe."
        
        # Note: genai library might need specific data structures for images
        response = await model.generate_content_async([
            prompt,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])
        
        result = response.text.strip().upper()
        if "SAFE" in result:
            return True, "OK"
        else:
            return False, response.text.strip()
    except Exception as e:
        print(f"[IMAGE] Safety check error: {e}")
        return True, "Safety check failed to run" # Fallback

def crop_resize_to_png_bytes(image_bytes: bytes, size: int = AVATAR_OUTPUT_SIZE) -> bytes:
    """Center-crop to a square, resize to `size`x`size`, return PNG bytes.

    PNG is used instead of JPEG so transparent images (RGBA mode) are preserved
    without alpha-channel loss. Single source of truth for avatar normalization —
    used by both the local saver (process_avatar) and the Cloudinary uploader (image_store).
    """
    img = Image.open(BytesIO(image_bytes))

    width, height = img.size
    new_size = min(width, height)
    left = (width - new_size) / 2
    top = (height - new_size) / 2
    img = img.crop((left, top, left + new_size, top + new_size))

    img = img.resize((size, size), Image.Resampling.LANCZOS)

    # Palette images must be converted before saving as PNG to avoid color issues.
    # RGBA and RGB are left as-is so the alpha channel is preserved.
    if img.mode == "P":
        img = img.convert("RGBA")

    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def save_png_bytes(png_bytes: bytes, filename_id: str) -> str:
    """Write already-encoded PNG bytes into the static avatars dir.

    Returns the filesystem path written. Centralizes the disk-write so the
    local-save fallback and process_avatar share one location.
    """
    save_dir = os.path.join("backend", "api", "static", "avatars")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{filename_id}.png")
    with open(save_path, "wb") as f:
        f.write(png_bytes)
    return save_path


def process_avatar(image_bytes: bytes, filename_id: str) -> str:
    """Accepts an image, center-crops, resizes, and saves it locally.

    Returns the filesystem path. Kept as the local-disk path used as the
    Cloudinary fallback (see image_store.store_avatar).
    """
    return save_png_bytes(crop_resize_to_png_bytes(image_bytes), filename_id)
