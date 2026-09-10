"""Workspace isolation for the asset listing projection."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.api.routers import assets as assets_router
from backend.core import database
from backend.core.workspace_auth import SessionPrincipal


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def asset_scope_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "asset-scope.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setenv("AITOB_TESTING", "1")
    monkeypatch.setattr(assets_router, "ASSETS_DIR", str(tmp_path / "shared-assets"))
    Path(assets_router.ASSETS_DIR).mkdir()
    run(database.init_db())
    yield db_path


def _principal(workspace_id: str) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        role="owner",
        session_id=f"session-{workspace_id}",
    )


def test_asset_listing_never_enumerates_shared_legacy_files(asset_scope_db):
    async def verify():
        shared = Path(assets_router.ASSETS_DIR)
        (shared / "workspace-a-legacy.png").write_bytes(b"legacy-a")
        (shared / "workspace-b-legacy.png").write_bytes(b"legacy-b")
        await database.record_media_asset(
            workspace_id="workspace-a",
            asset_type="overlay_asset",
            owner_type="workspace",
            owner_id="workspace-a",
            storage_url="/static/assets/a-managed.png",
            storage_key="a-managed.png",
        )
        await database.record_media_asset(
            workspace_id="workspace-b",
            asset_type="overlay_asset",
            owner_type="workspace",
            owner_id="workspace-b",
            storage_url="/static/assets/b-managed.png",
            storage_key="b-managed.png",
        )

        listed = await assets_router.list_assets(_principal("workspace-a"))
        assert [item["name"] for item in listed["assets"]] == ["a-managed.png"]
        assert [item["storage_key"] for item in listed["managed_assets"]] == ["a-managed.png"]
        assert "workspace-b-legacy.png" not in str(listed)

    run(verify())
