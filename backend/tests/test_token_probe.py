import pytest
from unittest.mock import AsyncMock, patch
from backend.core.providers.startgg.client import StartGGClient

@pytest.mark.asyncio
async def test_probe_token_permissions_no_token():
    # If no token is provided and none in DB, returns appropriate error
    with patch("backend.core.database.get_setting", AsyncMock(return_value=None)), \
         patch("backend.core.database.get_connection", AsyncMock(return_value=None)):
        client = StartGGClient(token="")
        res = await client.probe_token_permissions()
        assert res["valid"] is False
        assert "No Start.gg API token configured" in res["error"]

@pytest.mark.asyncio
async def test_probe_token_permissions_invalid_token():
    # If token query raises error, returns valid=False
    client = StartGGClient(token="invalid_token")
    async def mock_query(query_str, variables=None):
        if "currentUser" in query_str:
            raise Exception("Invalid token")
        return {}
    
    with patch.object(client, "query", AsyncMock(side_effect=mock_query)):
        res = await client.probe_token_permissions()
        assert res["valid"] is False
        assert "Invalid token or network failure" in res["error"]

@pytest.mark.asyncio
async def test_probe_token_permissions_read_only_token():
    # If token query succeeds for currentUser but markSetInProgress raises "You do not have permission"
    client = StartGGClient(token="read_only_token")
    async def mock_query(query_str, variables=None):
        if "currentUser" in query_str:
            return {"currentUser": {"id": 12345, "name": "Test User"}}
        elif "markSetInProgress" in query_str:
            raise Exception("You do not have permission to do that")
        return {}

    with patch.object(client, "query", AsyncMock(side_effect=mock_query)):
        res = await client.probe_token_permissions()
        assert res["valid"] is True
        assert res["user_name"] == "Test User"
        assert res["has_write_scope"] is False
        assert "lacks tournament admin / T.O. write scopes" in res["error"]

@pytest.mark.asyncio
async def test_probe_token_permissions_full_to_token():
    # If markSetInProgress raises "Set not found" or "record not found"
    client = StartGGClient(token="full_to_token")
    async def mock_query(query_str, variables=None):
        if "currentUser" in query_str:
            return {"currentUser": {"id": 12345, "name": "Admin User"}}
        elif "markSetInProgress" in query_str:
            raise Exception("Start.gg API Error: Set not found")
        return {}

    with patch.object(client, "query", AsyncMock(side_effect=mock_query)):
        res = await client.probe_token_permissions()
        assert res["valid"] is True
        assert res["user_name"] == "Admin User"
        assert res["has_write_scope"] is True
        assert res["error"] is None
