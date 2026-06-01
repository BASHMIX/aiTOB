import pytest
from unittest.mock import patch
from PIL import Image
import io
import os

from backend.core.image_utils import process_avatar

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
