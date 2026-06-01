import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from backend.core.image_utils import validate_avatar_safety

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
