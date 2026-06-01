import pytest
from backend.core.providers.startgg.mapper import _extract_avatar

def test_extract_avatar_empty_inputs():
    assert _extract_avatar(None) is None
    assert _extract_avatar([]) is None

def test_extract_avatar_no_user():
    participants = [{"participantId": 123}]
    assert _extract_avatar(participants) is None

def test_extract_avatar_user_no_images():
    participants = [{"user": {"id": 123}}]
    assert _extract_avatar(participants) is None

def test_extract_avatar_user_empty_images():
    participants = [{"user": {"id": 123, "images": []}}]
    assert _extract_avatar(participants) is None

def test_extract_avatar_has_profile_image():
    participants = [{
        "user": {
            "id": 123,
            "images": [
                {"type": "banner", "url": "http://example.com/banner.jpg"},
                {"type": "profile", "url": "http://example.com/profile.jpg"}
            ]
        }
    }]
    assert _extract_avatar(participants) == "http://example.com/profile.jpg"

def test_extract_avatar_fallback_first_image():
    participants = [{
        "user": {
            "id": 123,
            "images": [
                {"type": "banner", "url": "http://example.com/banner.jpg"},
                {"type": "other", "url": "http://example.com/other.jpg"}
            ]
        }
    }]
    assert _extract_avatar(participants) == "http://example.com/banner.jpg"

def test_extract_avatar_multiple_participants_skip_missing():
    participants = [
        {"participantId": 1},  # No user
        {"user": {"id": 2}},   # User, no images
        {"user": {"id": 3, "images": [{"type": "profile", "url": "http://example.com/p3.jpg"}]}}
    ]
    assert _extract_avatar(participants) == "http://example.com/p3.jpg"
