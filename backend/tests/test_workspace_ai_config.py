"""Workspace assistant configuration and account-selection contracts."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from backend.core import database
from backend.core.ai_service import (
    AIConfigurationError,
    AIService,
    AIServiceError,
    get_workspace_ai_config,
    set_workspace_ai_key,
    update_workspace_ai_config,
)
from backend.tests.fixtures.tournament_setup.adapters import FakeWorkspaceAIAdapter


@pytest.fixture
async def workspace_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "workspace-ai-config.pg"))
    monkeypatch.setenv("AITOB_INTEGRATION_MASTER_KEY", Fernet.generate_key().decode("ascii"))
    await database.init_db()
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES ('w-a', 'workspace-a', 'A')")
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES ('w-b', 'workspace-b', 'B')")
        await db.commit()


@pytest.mark.asyncio
async def test_policy_is_immutable_and_unknown_workspace_is_rejected(workspace_db):
    with pytest.raises(AIConfigurationError):
        await get_workspace_ai_config("missing-workspace")
    current = await get_workspace_ai_config("w-a")
    with pytest.raises(AIConfigurationError):
        await update_workspace_ai_config("w-a", {"policy_version": "legacy-policy"})
    assert (await get_workspace_ai_config("w-a"))["policy_version"] == current["policy_version"]


@pytest.mark.asyncio
async def test_disabled_connection_can_rotate_without_being_reenabled(workspace_db):
    await set_workspace_ai_key("w-a", "gemini", "first-key")
    config = await get_workspace_ai_config("w-a")
    account_id = config["connections"]["gemini"]["account_id"]
    from backend.core import integrations

    await integrations.disable_integration_account(account_id, workspace_id="w-a")
    result = await set_workspace_ai_key("w-a", "gemini", "replacement-key")
    assert result["account_id"] == account_id
    assert (await get_workspace_ai_config("w-a"))["connections"]["gemini"]["enabled"] is False
    assert (await integrations.get_integration_secret(account_id, "api_key")) == "replacement-key"


@pytest.mark.asyncio
async def test_workspace_service_wraps_unclassified_provider_errors(workspace_db):
    await database.upsert_tournament(
        "w-a/t", "Tournament", "SF6", "event", "SF6", "{}", workspace_id="w-a"
    )
    await set_workspace_ai_key("w-a", "gemini", "workspace-key")
    await update_workspace_ai_config("w-a", {"mode": "read_only"})

    class Broken(FakeWorkspaceAIAdapter):
        async def complete(self, **kwargs):
            raise RuntimeError("opaque upstream response containing workspace-key")

    with pytest.raises(AIServiceError) as caught:
        await AIService({"gemini": Broken("gemini")}).answer(
            tournament_slug="w-a/t", question="What is pending?", workspace_id="w-a"
        )
    assert caught.value.failure_category == "unknown"
    assert "workspace-key" not in str(caught.value)


@pytest.mark.asyncio
async def test_legacy_graph_requires_workspace_and_uses_selected_account(monkeypatch):
    from backend.bot.agent import graph

    class FakeLLM:
        def with_structured_output(self, schema):
            return (self, schema)

    captured = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def with_structured_output(self, schema):
            return (self, schema)

    async def fake_config(workspace_id):
        assert workspace_id == "workspace-a"
        return {
            "provider_type": "gemini",
            "model": "workspace-model",
            "mode": "read_only",
            "selected_account_id": "account-a",
        }

    async def fake_key(workspace_id, config):
        assert workspace_id == "workspace-a"
        assert config["selected_account_id"] == "account-a"
        return "workspace-only-key"

    import backend.core.ai_service as ai_service

    monkeypatch.setattr(ai_service, "get_workspace_ai_config", fake_config)
    monkeypatch.setattr(ai_service, "_workspace_api_key", fake_key)
    monkeypatch.setattr(graph, "ChatGoogleGenerativeAI", FakeChat)
    with pytest.raises(AIConfigurationError):
        await graph._get_llm()
    await graph._get_llm("workspace-a")
    assert captured["api_key"] == "workspace-only-key"
    assert captured["model"] == "workspace-model"
