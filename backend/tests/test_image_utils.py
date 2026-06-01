from backend.core.image_utils import validate_avatar_quality
from PIL import Image
import io

def generate_image_bytes(width, height, format='JPEG', padding=0):
    img = Image.new('RGB', (width, height), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format=format)
    img_bytes = img_byte_arr.getvalue()
    if padding > 0:
        img_bytes += b'\x00' * padding
    return img_bytes

def test_validate_avatar_quality_valid():
    """Test with a valid 200x200 image."""
    img_bytes = generate_image_bytes(200, 200)
    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is True
    assert msg == "OK"

def test_validate_avatar_quality_low_resolution():
    """Test with images smaller than 100x100."""
    # Both width and height too small
    img_bytes = generate_image_bytes(50, 50)
    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is False
    assert "resolution is too low" in msg

    # Width too small
    img_bytes = generate_image_bytes(99, 100)
    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is False
    assert "resolution is too low" in msg

    # Height too small
    img_bytes = generate_image_bytes(100, 99)
    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is False
    assert "resolution is too low" in msg

def test_validate_avatar_quality_too_large():
    """Test with an image larger than 5MB."""
    # Generate a normal image but pad it to be over 5MB
    # 5MB = 5 * 1024 * 1024 = 5242880 bytes
    base_bytes = generate_image_bytes(200, 200)
    padding_needed = (5 * 1024 * 1024) + 1 - len(base_bytes)
    img_bytes = generate_image_bytes(200, 200, padding=padding_needed)

    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is False
    assert "size is too large" in msg

def test_validate_avatar_quality_aspect_ratio_too_high():
    """Test with images that are too narrow or too wide (ratio > 3.0)."""
    # Width is much larger than height
    img_bytes = generate_image_bytes(301, 100)
    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is False
    assert "too narrow or too wide" in msg

    # Height is much larger than width
    img_bytes = generate_image_bytes(100, 301)
    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is False
    assert "too narrow or too wide" in msg

    # Edge case: exactly 3.0 should be valid
    img_bytes = generate_image_bytes(300, 100)
    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is True
    assert msg == "OK"

def test_validate_avatar_quality_invalid_image():
    """Test with invalid image bytes."""
    img_bytes = b"This is not a real image"
    is_valid, msg = validate_avatar_quality(img_bytes)
    assert is_valid is False
    assert "Invalid image file" in msg
