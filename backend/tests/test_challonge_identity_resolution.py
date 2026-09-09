"""Phase-4 identity-only resolver safety and persistence tests."""
from __future__ import annotations

import asyncio

from backend.core.storage import dbapi as aiosqlite
import pytest

from backend.core import challonge_resolution as resolution
from backend.core import database
from backend.core.providers.challonge.client import ChallongeError
from backend.core.providers.challonge.locator import parse_locator
from backend.core.sync_coordinator import SyncCoordinator


class _ResolverAdapter:
    """A read-only adapter double: no participant/match/mutation method exists."""

    def __init__(self, *, hold: bool = False) -> None:
        self.provider_account_id = "default"
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.hold = hold

    async def resolve(self, identifier: str, subdomain: str | None = None) -> dict:
        self.calls += 1
        self.started.set()
        if self.hold:
            await self.release.wait()
        # A provider response is authoritative about the applicable community.
        return {
            "provider_type": "challonge",
            "provider_account_id": self.provider_account_id,
            "provider_tournament_id": "18449397",
            "name": "Friday Night Championship",
            "subdomain": "fnc-jo",
            "url_slug": "ap6fj0k1",
            "state": "pending",
            "format": "double elimination",
            "locator_key": parse_locator(identifier, subdomain).coordination_key,
        }


@pytest.fixture
async def isolated_identity_db(tmp_path, monkeypatch):
    db_path = tmp_path / "identity.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    await database.init_db()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO integration_accounts (id, owner_id, provider_type, external_account_id, display_name)
               VALUES ('account-fnc', 'admin', 'challonge', 'test-account', 'Test Challonge')"""
        )
        await db.commit()
    return db_path


@pytest.mark.asyncio
async def test_identifier_forms_persist_one_account_and_community_scoped_record(
    isolated_identity_db, monkeypatch
):
    adapter = _ResolverAdapter()
    service = resolution.ChallongeResolutionService(SyncCoordinator())
    adapter.provider_account_id = "account-fnc"
    monkeypatch.setattr(resolution, "ChallongeProvider", lambda provider_account_id: adapter)

    stored = []
    for value, subdomain in [
        ("18449397", None),
        ("https://challonge.com/AP6FJ0K1/", None),
        ("https://fnc-jo.challonge.com/ap6fj0k1", None),
        ("18449397@fnc-jo", None),
    ]:
        resolved = await service.resolve("account-fnc", value, subdomain)
        stored.append(await database.persist_challonge_identity(
            resolved, locator_key=resolved["locator_key"]
        ))

    assert {row["slug"] for row in stored} == {"challonge:account-fnc:fnc-jo:18449397"}
    assert {row["provider_account_id"] for row in stored} == {"account-fnc"}
    assert {row["provider_subdomain"] for row in stored} == {"fnc-jo"}
    # Four distinct user forms each issue only the minimal metadata resolve; no
    # bracket, participant, or mutation request is available on this adapter.
    assert adapter.calls == 4


@pytest.mark.asyncio
async def test_duplicate_concurrent_resolve_joins_one_coordinator_operation(
    isolated_identity_db, monkeypatch
):
    adapter = _ResolverAdapter(hold=True)
    service = resolution.ChallongeResolutionService(SyncCoordinator())
    adapter.provider_account_id = "account-fnc"
    monkeypatch.setattr(resolution, "ChallongeProvider", lambda provider_account_id: adapter)

    first = asyncio.create_task(service.resolve("account-fnc", "https://fnc-jo.challonge.com/ap6fj0k1"))
    await adapter.started.wait()
    # Case and trailing slash normalize to the same coordinator key.
    second = asyncio.create_task(service.resolve("account-fnc", "https://FNC-JO.challonge.com/AP6FJ0K1/"))
    # Database alias lookup is async I/O; wait for the second caller to reach
    # coordinator admission while the first adapter operation remains held.
    try:
        async with asyncio.timeout(10):
            while len(service._coordinator.telemetry) < 2:
                await asyncio.sleep(0.01)
        assert [entry.disposition for entry in service._coordinator.telemetry] == ["started", "joined"]
    finally:
        adapter.release.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert adapter.calls == 1
    assert first_result["provider_tournament_id"] == second_result["provider_tournament_id"]


@pytest.mark.asyncio
async def test_saved_fresh_alias_skips_a_second_provider_resolve(
    isolated_identity_db, monkeypatch
):
    adapter = _ResolverAdapter()
    service = resolution.ChallongeResolutionService(SyncCoordinator())
    adapter.provider_account_id = "account-fnc"
    monkeypatch.setattr(resolution, "ChallongeProvider", lambda provider_account_id: adapter)
    first = await service.resolve("account-fnc", "https://fnc-jo.challonge.com/ap6fj0k1")
    await database.persist_challonge_identity(first, locator_key=first["locator_key"])
    cached = await service.resolve("account-fnc", "https://FNC-JO.challonge.com/AP6FJ0K1/")

    assert adapter.calls == 1
    assert cached["cached"] is True
    assert cached["tournament_slug"] == "challonge:account-fnc:fnc-jo:18449397"


@pytest.mark.asyncio
async def test_preview_then_import_reuses_short_lived_safe_identity_metadata(
    isolated_identity_db, monkeypatch
):
    adapter = _ResolverAdapter()
    service = resolution.ChallongeResolutionService(SyncCoordinator())
    adapter.provider_account_id = "account-fnc"
    monkeypatch.setattr(resolution, "ChallongeProvider", lambda provider_account_id: adapter)
    preview = await service.resolve("account-fnc", "https://fnc-jo.challonge.com/ap6fj0k1")
    imported_identity = await service.resolve("account-fnc", "https://FNC-JO.challonge.com/AP6FJ0K1/")
    stored = await database.persist_challonge_identity(
        imported_identity, locator_key=imported_identity["locator_key"]
    )

    assert adapter.calls == 1
    assert imported_identity["cached"] is True
    assert stored["slug"] == "challonge:account-fnc:fnc-jo:18449397"


@pytest.mark.asyncio
async def test_duplicate_concurrent_imports_keep_one_canonical_record(isolated_identity_db):
    resolved = {
        "provider_type": "challonge",
        "provider_account_id": "account-fnc",
        "provider_tournament_id": "18449397",
        "name": "Friday Night Championship",
        "subdomain": "fnc-jo",
        "state": "pending",
    }
    first, second = await asyncio.gather(
        database.persist_challonge_identity(
            resolved, locator_key="id:fnc-jo:18449397"
        ),
        database.persist_challonge_identity(
            resolved, locator_key="slug:fnc-jo:ap6fj0k1"
        ),
    )

    assert first["slug"] == second["slug"] == "challonge:account-fnc:fnc-jo:18449397"
    tournaments = await database.get_tournaments()
    assert [row["slug"] for row in tournaments if row["provider_type"] == "challonge"] == [
        "challonge:account-fnc:fnc-jo:18449397"
    ]


@pytest.mark.asyncio
async def test_unsafe_locator_is_rejected_before_adapter_or_network(monkeypatch):
    called = False

    def no_adapter(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unsafe input must never reach adapter construction")

    service = resolution.ChallongeResolutionService(SyncCoordinator())
    monkeypatch.setattr(resolution, "ChallongeProvider", no_adapter)

    with pytest.raises(ValueError):
        await service.resolve("account-fnc", "https://user:secret-token@challonge.com/ap6fj0k1")

    assert called is False


@pytest.mark.asyncio
async def test_challonge_provider_exposes_no_phase4_mutation_path():
    from backend.core.providers.challonge.provider import ChallongeProvider

    provider = ChallongeProvider(client=object())
    score = await provider.report_score("challonge:18449397:1", "p1", "p1", "p2", 1, 0)
    start = await provider.start_tournament("18449397")
    active = await provider.mark_in_progress("challonge:18449397:1")

    assert not score.success and not start.success and not active.success


def test_provider_error_messages_do_not_reflect_credentials():
    secret = "secret-token"
    # The public exception type deliberately has no response body attached.
    error = ChallongeError("Challonge rejected the request.")
    assert secret not in str(error)


@pytest.mark.asyncio
async def test_provider_route_never_reflects_a_provider_exception_token(monkeypatch):
    from fastapi import HTTPException
    from backend.api.routers import providers
    from backend.api.schemas import ChallongeResolveRequest

    class FailingResolution:
        async def resolve(self, *_args, **_kwargs):
            raise ChallongeError("secret-token")

    monkeypatch.setattr(providers, "resolution_service", FailingResolution())
    monkeypatch.setattr(
        providers, "get_provider_feature_flags", lambda: type("Flags", (), {"challonge_read_enabled": True})()
    )
    with pytest.raises(HTTPException) as exc:
            await providers.resolve_tournament(
            "challonge", ChallongeResolveRequest(identifier="18449397", provider_account_id="account-fnc")
            )

    assert exc.value.status_code == 422
    assert exc.value.detail == "Challonge request could not be completed."
