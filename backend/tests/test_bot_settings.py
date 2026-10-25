"""Tests for multi-tenant workspace bot settings and customization."""

from unittest.mock import AsyncMock
import pytest
from httpx import AsyncClient, ASGITransport
from backend.api.main import app
from backend.core import database
from backend.core.database import (
    get_workspace_bot_settings,
    upsert_workspace_bot_settings,
)
from backend.core.workspace_auth import SessionPrincipal


async def _ensure_workspace(workspace_id: str, slug: str = "test-ws"):
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute(
            "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (workspace_id, slug, f"Workspace {slug}"),
        )
        await db.commit()


@pytest.mark.asyncio
async def test_workspace_bot_settings_default_fallback():
    """An unconfigured workspace receives clean default settings."""
    settings = await get_workspace_bot_settings("non-existent-workspace-xyz")
    assert settings["enable_rules_command"] is True
    assert settings["enable_avatar_uploads"] is True
    assert settings["enable_match_threads"] is True
    assert settings["response_mode"] == "direct_template"
    assert settings["custom_rules_markdown"] == ""


@pytest.mark.asyncio
async def test_workspace_bot_settings_persistence_and_isolation():
    """Settings are isolated per workspace and updated accurately."""
    ws_a = "workspace-alpha-test"
    ws_b = "workspace-beta-test"

    await _ensure_workspace(ws_a, "alpha")
    await _ensure_workspace(ws_b, "beta")

    # Upsert for workspace A
    saved_a = await upsert_workspace_bot_settings(
        ws_a,
        custom_rules_markdown="## Alpha Tournament Rules\n- Rule 1\n- Rule 2",
        welcome_message="Welcome to Alpha Cup!",
        enable_avatar_uploads=False,
        response_mode="llm_assistant",
    )
    assert saved_a["enable_avatar_uploads"] is False
    assert saved_a["response_mode"] == "llm_assistant"
    assert "Alpha Cup" in saved_a["welcome_message"]

    # Verify workspace B remains clean and unaffected
    settings_b = await get_workspace_bot_settings(ws_b)
    assert settings_b["enable_avatar_uploads"] is True
    assert settings_b["response_mode"] == "direct_template"
    assert settings_b["welcome_message"] == ""

    # Re-fetch workspace A to verify durability
    recheck_a = await get_workspace_bot_settings(ws_a)
    assert recheck_a["custom_rules_markdown"] == "## Alpha Tournament Rules\n- Rule 1\n- Rule 2"
    assert recheck_a["enable_avatar_uploads"] is False
    assert recheck_a["response_mode"] == "llm_assistant"


@pytest.mark.asyncio
async def test_bot_settings_api_patch_and_get(monkeypatch):
    """Authenticated workspace organizer can fetch and patch bot settings via API."""
    workspace_id = "ws-api-bot-test"
    await _ensure_workspace(workspace_id, "api-bot")

    principal = SessionPrincipal(
        user_id="user-to-test",
        workspace_id=workspace_id,
        role="tournament_organizer",
        session_id=f"sess-{workspace_id}",
    )
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    transport = ASGITransport(app=app)
    cookies = {"aitob_session": "mock-token"}

    async with AsyncClient(transport=transport, base_url="http://testserver", cookies=cookies) as client:
        # 1. GET initial settings
        get_res = await client.get("/api/workspace/bot-settings")
        assert get_res.status_code == 200
        initial_data = get_res.json()["settings"]
        assert initial_data["enable_rules_command"] is True

        # 2. PATCH custom rules and toggle
        patch_payload = {
            "custom_rules_markdown": "### Official Rules\n1. Bring your own controller\n2. FT2 until Top 8",
            "welcome_message": "Welcome to the SF6 Major!",
            "enable_avatar_uploads": False,
            "response_mode": "direct_template",
        }
        patch_res = await client.patch("/api/workspace/bot-settings", json=patch_payload)
        assert patch_res.status_code == 200
        patched_data = patch_res.json()["settings"]
        assert patched_data["enable_avatar_uploads"] is False
        assert "Bring your own controller" in patched_data["custom_rules_markdown"]

        # 3. Re-GET to verify persistence
        verify_res = await client.get("/api/workspace/bot-settings")
        assert verify_res.status_code == 200
        assert verify_res.json()["settings"]["custom_rules_markdown"] == patch_payload["custom_rules_markdown"]


@pytest.mark.asyncio
async def test_bot_settings_preview_test(monkeypatch):
    """Organizer can send a test preview embed to a Discord channel."""
    workspace_id = "ws-api-bot-test"
    await _ensure_workspace(workspace_id, "api-bot-preview")

    principal = SessionPrincipal(
        user_id="user-to-test",
        workspace_id=workspace_id,
        role="tournament_organizer",
        session_id=f"sess-{workspace_id}",
    )
    monkeypatch.setattr("backend.api.auth.get_session_principal", AsyncMock(return_value=principal))

    transport = ASGITransport(app=app)
    cookies = {"aitob_session": "mock-token"}

    async with AsyncClient(transport=transport, base_url="http://testserver", cookies=cookies) as client:
        # Case 1: No active Discord account connected
        res_disconnected = await client.post("/api/workspace/bot-settings/preview-test")
        assert res_disconnected.status_code == 200
        assert res_disconnected.json()["ok"] is False
        assert "No active Discord server connected" in res_disconnected.json()["message"]

        # Case 2: Active Discord account and destination configured
        mock_accounts = [{"id": "acc-discord-1", "provider_type": "discord", "status": "active"}]
        mock_destinations = [{"destination_type": "match_call_channel", "destination_external_id": "123456789"}]
        mock_send = AsyncMock(return_value="msg-12345")

        monkeypatch.setattr("backend.core.integrations.list_integration_accounts", AsyncMock(return_value=mock_accounts))
        monkeypatch.setattr("backend.core.integrations.list_integration_destinations", AsyncMock(return_value=mock_destinations))
        monkeypatch.setattr("backend.core.discord_api.send_channel_embed", mock_send)

        res_connected = await client.post("/api/workspace/bot-settings/preview-test")
        assert res_connected.status_code == 200
        assert res_connected.json()["ok"] is True
        mock_send.assert_called_once()

