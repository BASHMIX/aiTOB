import pytest
from PIL import Image
from io import BytesIO
from backend.core.image_utils import validate_avatar_quality

def create_image_bytes(width: int, height: int, format: str = "JPEG") -> bytes:
    """Helper to create dummy image bytes."""
    img = Image.new("RGB", (width, height), color="red")
    buf = BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()

def test_validate_avatar_quality_valid():
    """Test with a perfectly valid image."""
    image_bytes = create_image_bytes(200, 200)
    is_valid, msg = validate_avatar_quality(image_bytes)
    assert is_valid is True
    assert msg == "OK"

def test_validate_avatar_quality_low_resolution():
    """Test with an image below 100x100 resolution."""
    # Both width and height < 100
    image_bytes = create_image_bytes(50, 50)
    is_valid, msg = validate_avatar_quality(image_bytes)
    assert is_valid is False
    assert "resolution is too low" in msg

    # Width < 100
    image_bytes_w = create_image_bytes(99, 200)
    is_valid_w, msg_w = validate_avatar_quality(image_bytes_w)
    assert is_valid_w is False
    assert "resolution is too low" in msg_w

    # Height < 100
    image_bytes_h = create_image_bytes(200, 99)
    is_valid_h, msg_h = validate_avatar_quality(image_bytes_h)
    assert is_valid_h is False
    assert "resolution is too low" in msg_h

def test_validate_avatar_quality_large_file_size():
    """Test with an image file size exceeding 5MB."""
    base_image_bytes = create_image_bytes(200, 200)
    # Append enough garbage bytes to exceed 5MB (5 * 1024 * 1024 bytes)
    # Image.open will often still read the initial valid image headers and ignore the trailing garbage,
    # but the overall bytes length will trigger the check.
    large_image_bytes = base_image_bytes + b"0" * (5 * 1024 * 1024)
    is_valid, msg = validate_avatar_quality(large_image_bytes)
    assert is_valid is False
    assert "too large" in msg

def test_validate_avatar_quality_invalid_aspect_ratio():
    """Test with an image where aspect ratio > 3.0."""
    # Width much larger than height
    wide_bytes = create_image_bytes(301, 100)
    is_valid_w, msg_w = validate_avatar_quality(wide_bytes)
    assert is_valid_w is False
    assert "narrow or too wide" in msg_w

    # Height much larger than width
    tall_bytes = create_image_bytes(100, 301)
    is_valid_t, msg_t = validate_avatar_quality(tall_bytes)
    assert is_valid_t is False
    assert "narrow or too wide" in msg_t

def test_validate_avatar_quality_invalid_data():
    """Test with non-image bytes."""
    garbage_bytes = b"this is not an image"
    is_valid, msg = validate_avatar_quality(garbage_bytes)
    assert is_valid is False
    assert "Invalid image file" in msg
