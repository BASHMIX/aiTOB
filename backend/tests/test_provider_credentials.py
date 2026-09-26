from __future__ import annotations

import httpx
import pytest

from backend.api.routers import integrations as integrations_router
from backend.api.schemas import ProviderCredentialConnectRequest
from backend.core import database, integrations
from backend.core.provider_credentials import verify_provider_credential
from backend.core.storage import dbapi
from backend.core.workspace_auth import SessionPrincipal


@pytest.mark.asyncio
async def test_startgg_credential_derives_identity_from_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer owner-token"
        return httpx.Response(200, json={"data": {"currentUser": {
            "id": 987, "name": "Organizer", "slug": "owner", "player": {"gamerTag": "FNC"},
        }}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        verified = await verify_provider_credential("startgg", "owner-token", http=http)

    assert verified.external_account_id == "987"
    assert verified.display_name == "FNC"
    assert verified.secret_type == "access_token"
    assert verified.metadata["identity_verified"] is True


@pytest.mark.asyncio
async def test_challonge_credential_derives_identity_from_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "owner-api-key"
        assert request.headers["authorization-type"] == "v1"
        return httpx.Response(200, json={"data": {
            "id": "challonge-42", "attributes": {"username": "FNC Brackets"},
        }})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        verified = await verify_provider_credential("challonge", "owner-api-key", http=http)

    assert verified.external_account_id == "challonge-42"
    assert verified.display_name == "FNC Brackets"
    assert verified.secret_type == "api_key"


@pytest.mark.asyncio
async def test_connect_provider_credential_stores_verified_workspace_identity(monkeypatch):
    monkeypatch.setenv("AITOB_INTEGRATION_MASTER_KEY", "7lXNrOpw2HnqGYiRkqzGN70KGyxoDpcQ0H3jDXiVlvc=")
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", ("byoc-w", "byoc-w", "BYOC"))
        await db.commit()

    async def verified(_provider: str, _credential: str):
        from backend.core.provider_credentials import VerifiedProviderCredential
        return VerifiedProviderCredential(
            provider_type="startgg", external_account_id="owner-123",
            display_name="Verified Owner", secret_type="access_token",
            metadata={"identity_verified": True},
        )

    monkeypatch.setattr(integrations_router, "verify_provider_credential", verified)
    result = await integrations_router.connect_provider_credential(
        ProviderCredentialConnectRequest(provider_type="startgg", credential="private-owner-token"),
        SessionPrincipal(user_id="owner", workspace_id="byoc-w", role="owner", session_id="session"),
    )

    account = result["account"]
    assert account["external_account_id"] == "owner-123"
    assert account["display_name"] == "Verified Owner"
    assert result["credential_owner"] == "workspace"
    assert await integrations.get_integration_secret(account["id"], "access_token") == "private-owner-token"


@pytest.mark.asyncio
async def test_generic_provider_identity_creation_is_rejected():
    from fastapi import HTTPException
    from backend.api.schemas import IntegrationAccountRequest

    with pytest.raises(HTTPException, match="verified BYOC"):
        await integrations_router.create_account(
            IntegrationAccountRequest(
                provider_type="startgg", external_account_id="typed-id", display_name="Typed name"
            ),
            SessionPrincipal(user_id="owner", workspace_id="byoc-w", role="owner", session_id="session"),
        )


@pytest.mark.asyncio
async def test_managed_provider_oauth_is_dark_by_default(monkeypatch):
    from backend.api.routers import provider_oauth

    monkeypatch.delenv("AITOB_MANAGED_PROVIDER_OAUTH", raising=False)
    monkeypatch.setenv("STARTGG_CLIENT_ID", "platform-client")
    monkeypatch.setenv("STARTGG_CLIENT_SECRET", "platform-secret")
    monkeypatch.setenv("STARTGG_OAUTH_REDIRECT_URI", "https://example.test/api/auth/providers/startgg/callback")
    assert await provider_oauth._oauth_available("startgg") is False


@pytest.mark.asyncio
async def test_verified_byoc_upgrades_one_legacy_account_in_place(monkeypatch):
    monkeypatch.setenv("AITOB_INTEGRATION_MASTER_KEY", "7lXNrOpw2HnqGYiRkqzGN70KGyxoDpcQ0H3jDXiVlvc=")
    async with dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)", ("legacy-w", "legacy-w", "Legacy"))
        await db.commit()
    legacy = await integrations.create_integration_account("legacy-w", "startgg", "legacy", "Migrated Start.gg")

    async def verified(_provider: str, _credential: str):
        from backend.core.provider_credentials import VerifiedProviderCredential
        return VerifiedProviderCredential(
            provider_type="startgg", external_account_id="real-owner",
            display_name="Real Owner", secret_type="access_token",
            metadata={"identity_verified": True},
        )

    monkeypatch.setattr(integrations_router, "verify_provider_credential", verified)
    result = await integrations_router.connect_provider_credential(
        ProviderCredentialConnectRequest(provider_type="startgg", credential="new-owner-token"),
        SessionPrincipal(user_id="owner", workspace_id="legacy-w", role="owner", session_id="session"),
    )

    assert result["account"]["id"] == legacy["id"]
    updated = await integrations.get_integration_account(legacy["id"], workspace_id="legacy-w")
    assert updated["external_account_id"] == "real-owner"
    assert updated["display_name"] == "Real Owner"
