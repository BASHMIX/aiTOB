"""Commit #10 Part B hotfix tests: removeStream no-op + Gemini vision model."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from backend.core.providers.startgg.client import StartGGClient
from backend.core.image_utils import validate_avatar_safety


# ── B2: removeStream is a safe no-op (start.gg has no such mutation) ───────
@pytest.mark.asyncio
async def test_remove_stream_is_noop_and_never_queries():
    client = StartGGClient(token="dummy")
    # If remove_stream ever calls the GraphQL endpoint again, this blows up.
    client.query = AsyncMock(side_effect=AssertionError("remove_stream must not hit the API"))

    ok = await client.remove_stream("12345")
    assert ok is True
    client.query.assert_not_called()


@pytest.mark.asyncio
async def test_remove_stream_query_is_undefined():
    # The non-existent mutation must not be importable anymore.
    import backend.core.providers.startgg.queries as q
    assert not hasattr(q, "REMOVE_STREAM")


# ── B3: avatar safety uses a current vision model (env-overridable) ───────
@pytest.mark.asyncio
@patch("backend.core.image_utils.genai.GenerativeModel")
@patch("backend.core.image_utils.genai.configure")
async def test_safety_defaults_to_gemini_25_flash(mock_configure, mock_model, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.delenv("GEMINI_VISION_MODEL", raising=False)
    inst = MagicMock()
    inst.generate_content_async = AsyncMock(return_value=MagicMock(text="SAFE"))
    mock_model.return_value = inst

    await validate_avatar_safety(b"img")
    mock_model.assert_called_once_with("gemini-2.5-flash")


@pytest.mark.asyncio
@patch("backend.core.image_utils.genai.GenerativeModel")
@patch("backend.core.image_utils.genai.configure")
async def test_safety_respects_env_override(mock_configure, mock_model, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")
    inst = MagicMock()
    inst.generate_content_async = AsyncMock(return_value=MagicMock(text="SAFE"))
    mock_model.return_value = inst

    await validate_avatar_safety(b"img")
    mock_model.assert_called_once_with("gemini-2.0-flash")
