import io
import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from PIL import Image

from backend.core.image_utils import (
    validate_avatar_quality,
    process_avatar,
    validate_avatar_safety,
)


# ===== from PR #21 =====

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

# ===== from PR #43 =====

def create_test_image_bytes(size=(800, 600), color="red", mode="RGB"):
    """Helper to create an in-memory image and return its bytes."""
    img = Image.new(mode, size, color=color)
    img_bytes = io.BytesIO()
    # P mode needs a different format like PNG or GIF to save directly to bytes in this simple way without palette setup
    format = "PNG" if mode in ("RGBA", "P") else "JPEG"
    img.save(img_bytes, format=format)
    return img_bytes.getvalue()

def test_process_avatar_saves_correctly(tmp_path):
    # Setup a simple RGB image
    image_bytes = create_test_image_bytes(size=(800, 600), mode="RGB")

    original_join = os.path.join
    def mock_join(*args):
        if len(args) == 4 and args == ("backend", "api", "static", "avatars"):
            return str(tmp_path)
        return original_join(*args)

    with patch("os.path.join", side_effect=mock_join):
        saved_path = process_avatar(image_bytes, "test_rgb_avatar")

        # Verify the file was saved
        assert os.path.exists(saved_path)
        assert str(tmp_path) in saved_path
        assert saved_path.endswith("test_rgb_avatar.jpg")

        # Verify crop and resize
        saved_img = Image.open(saved_path)
        assert saved_img.size == (500, 500)
        assert saved_img.mode == "RGB"
        assert saved_img.format == "JPEG"

def test_process_avatar_rgba_conversion(tmp_path):
    # Setup an RGBA image
    image_bytes = create_test_image_bytes(size=(1000, 1000), mode="RGBA")

    original_join = os.path.join
    def mock_join(*args):
        if len(args) == 4 and args == ("backend", "api", "static", "avatars"):
            return str(tmp_path)
        return original_join(*args)

    with patch("os.path.join", side_effect=mock_join):
        saved_path = process_avatar(image_bytes, "test_rgba_avatar")

        # Verify conversion to RGB and JPEG format
        saved_img = Image.open(saved_path)
        assert saved_img.size == (500, 500)
        assert saved_img.mode == "RGB"
        assert saved_img.format == "JPEG"

def test_process_avatar_cropping(tmp_path):
    # Create an image with a non-square aspect ratio to test cropping
    image_bytes = create_test_image_bytes(size=(1000, 500), color="blue", mode="RGB")

    original_join = os.path.join
    def mock_join(*args):
        if len(args) == 4 and args == ("backend", "api", "static", "avatars"):
            return str(tmp_path)
        return original_join(*args)

    with patch("os.path.join", side_effect=mock_join):
        saved_path = process_avatar(image_bytes, "test_crop_avatar")

        # Open and verify
        saved_img = Image.open(saved_path)
        assert saved_img.size == (500, 500)
        assert saved_img.mode == "RGB"
        # The center crop logic in the code:
        # width=1000, height=500
        # new_size=500
        # left=(1000-500)/2 = 250, top=(500-500)/2 = 0
        # right=750, bottom=500
        # Since the original image is uniformly blue, the result should also just be blue
        # But we at least verify the dimensions match 500x500

# ===== from PR #45 =====

@pytest.mark.asyncio
async def test_validate_avatar_safety_no_api_key():
    with patch('os.getenv', return_value=None):
        result, message = await validate_avatar_safety(b"fake_image_data")
        assert result is True
        assert message == "Safety check skipped (no API key)"

@pytest.mark.asyncio
@patch('backend.core.image_utils.genai.GenerativeModel')
@patch('backend.core.image_utils.genai.configure')
async def test_validate_avatar_safety_safe(mock_configure, mock_gen_model):
    with patch('os.getenv', return_value="fake_api_key"):
        mock_model_instance = MagicMock()
        mock_gen_model.return_value = mock_model_instance

        mock_response = MagicMock()
        mock_response.text = "This image is SAFE."
        mock_model_instance.generate_content_async = AsyncMock(return_value=mock_response)

        result, message = await validate_avatar_safety(b"fake_image_data")

        assert result is True
        assert message == "OK"
        mock_configure.assert_called_once_with(api_key="fake_api_key")
        mock_model_instance.generate_content_async.assert_called_once()

@pytest.mark.asyncio
@patch('backend.core.image_utils.genai.GenerativeModel')
@patch('backend.core.image_utils.genai.configure')
async def test_validate_avatar_safety_unsafe(mock_configure, mock_gen_model):
    with patch('os.getenv', return_value="fake_api_key"):
        mock_model_instance = MagicMock()
        mock_gen_model.return_value = mock_model_instance

        mock_response = MagicMock()
        mock_response.text = "OFFENSIVE CONTENT"
        mock_model_instance.generate_content_async = AsyncMock(return_value=mock_response)

        result, message = await validate_avatar_safety(b"fake_image_data")

        assert result is False
        assert message == "OFFENSIVE CONTENT"
        mock_configure.assert_called_once_with(api_key="fake_api_key")
        mock_model_instance.generate_content_async.assert_called_once()

@pytest.mark.asyncio
@patch('backend.core.image_utils.genai.GenerativeModel')
@patch('backend.core.image_utils.genai.configure')
async def test_validate_avatar_safety_exception(mock_configure, mock_gen_model):
    with patch('os.getenv', return_value="fake_api_key"):
        mock_model_instance = MagicMock()
        mock_gen_model.return_value = mock_model_instance

        mock_model_instance.generate_content_async = AsyncMock(side_effect=Exception("API Error"))

        result, message = await validate_avatar_safety(b"fake_image_data")

        assert result is True
        assert message == "Safety check failed to run"
        mock_configure.assert_called_once_with(api_key="fake_api_key")
        mock_model_instance.generate_content_async.assert_called_once()

