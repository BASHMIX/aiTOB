import pytest
from io import BytesIO
from PIL import Image
from backend.core.image_utils import validate_avatar_quality

def create_test_image(width, height, format="JPEG"):
    img = Image.new("RGB", (width, height), color="red")
    buf = BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()

def test_validate_avatar_quality_valid():
    image_bytes = create_test_image(200, 200)
    is_valid, msg = validate_avatar_quality(image_bytes)
    assert is_valid is True
    assert msg == "OK"

def test_validate_avatar_quality_invalid_bytes():
    is_valid, msg = validate_avatar_quality(b"not an image")
    assert is_valid is False
    assert "Invalid image file:" in msg

def test_validate_avatar_quality_too_small():
    image_bytes = create_test_image(50, 50)
    is_valid, msg = validate_avatar_quality(image_bytes)
    assert is_valid is False
    assert "Image resolution is too low" in msg

def test_validate_avatar_quality_too_large():
    # Create an image > 5MB by appending dummy bytes
    image_bytes = create_test_image(200, 200)
    padding = b"0" * (5 * 1024 * 1024 + 1)
    large_image_bytes = image_bytes + padding
    is_valid, msg = validate_avatar_quality(large_image_bytes)
    assert is_valid is False
    assert "File size is too large" in msg

def test_validate_avatar_quality_bad_aspect_ratio():
    image_bytes = create_test_image(400, 100)
    is_valid, msg = validate_avatar_quality(image_bytes)
    assert is_valid is False
    assert "The image is too narrow or too wide" in msg
