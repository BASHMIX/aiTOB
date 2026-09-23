"""Regression coverage for durable Discord Call delivery metadata."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


class _Message:
    id = 7301


class _Thread:
    id = 7201

    async def send(self, *args, **kwargs):
        return _Message()


class _Channel:
    async def create_thread(self, **kwargs):
        return _Thread()


class _Bot:
    def get_channel(self, channel_id):
        return _Channel()


class _RestoreBot(_Bot):
    def __init__(self):
        self.views = []

    def add_view(self, view, *, message_id):
        self.views.append((view, message_id))


@pytest.mark.asyncio
async def test_challonge_call_persists_thread_and_call_message_ids(monkeypatch):
    """A successful Call must leave a durable message ID for restart/audit."""
    from backend.bot import match_threads
    from backend.core import database

    # The PG acceptance fixture provides an empty disposable database; seed the
    # tournament through the repository boundary so the thread path is tested
    # against both PostgreSQL test storage and PostgreSQL runtime storage.
    await database.init_db()
    await database.upsert_tournament(
        "challonge:test", "Test Challonge", None, None, None, "{}",
        provider_type="challonge", provider_tournament_id="test",
        provider_account_id="account",
    )

    updates = []

    async def route(*args, **kwargs):
        return SimpleNamespace(channel_id="7001")

    async def update(match_id, **fields):
        updates.append(fields)

    async def no_timeout(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.core.bot_routing.resolve_discord_route", route)
    monkeypatch.setattr(match_threads, "update_active_match", update)
    monkeypatch.setattr(match_threads, "run_ready_check_timeout", no_timeout)

    await match_threads.create_match_thread(
        _Bot(),
        {"provider_type": "challonge", "discord_account_id": "account"},
        {
            "set_id": "challonge:test:match", "tournament_slug": "challonge:test",
            "p1_name": "One", "p2_name": "Two", "round_name": "Round 1",
            "p1_discord": "100", "p2_discord": "200", "workspace_id": "workspace",
        },
    )
    await asyncio.sleep(0)

    assert any(fields.get("discord_thread_id") == "7201" for fields in updates)
    assert any(fields.get("auto_dq_disarmed") == 1 for fields in updates)
    assert any(
        fields.get("thread_id") == "7201" and fields.get("call_message_id") == "7301"
        for fields in updates
    )


@pytest.mark.asyncio
async def test_startgg_call_uses_verified_entrant_links_for_mentions(monkeypatch):
    """Start.gg entrant links, not player-name similarity, drive recipients."""
    from backend.bot import match_threads
    from backend.core import database

    await database.init_db()
    updates = []

    async def route(*args, **kwargs):
        return SimpleNamespace(channel_id="7001")

    async def update(match_id, **fields):
        updates.append(fields)

    async def resolve(provider_type, tournament_slug, entrant_id, workspace_id=None):
        links = {"23741477": "624298189708722178", "23741309": "651677763664740362"}
        return links.get(str(entrant_id))

    async def no_timeout(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.core.bot_routing.resolve_discord_route", route)
    monkeypatch.setattr(match_threads, "update_active_match", update)
    monkeypatch.setattr(match_threads, "run_ready_check_timeout", no_timeout)
    monkeypatch.setattr("backend.core.identity_links.resolve_verified_discord_recipient", resolve)
    monkeypatch.setattr(match_threads, "get_discord_id_from_startgg", lambda *_args: _none())

    await match_threads.create_match_thread(
        _Bot(),
        {"provider_type": "startgg", "discord_account_id": "account", "check_in_source": "discord"},
        {
            "set_id": "107467304", "tournament_slug": "tournament/testfnc",
            "p1_name": "FGC | FNCeSports", "p2_name": "FNC | BASHMIX",
            "p1_entrant_id": "23741477", "p2_entrant_id": "23741309",
            "round_name": "Winners Semi-Final", "workspace_id": "workspace",
        },
    )
    await asyncio.sleep(0)
    assert any(fields.get("p1_discord") == "624298189708722178" for fields in updates)
    assert any(fields.get("p2_discord") == "651677763664740362" for fields in updates)


async def _none():
    return None


@pytest.mark.asyncio
async def test_called_challonge_view_is_persistent_and_restored_after_restart(monkeypatch):
    """A process restart must not turn an already-sent Ready button inert."""
    from backend.bot import match_threads

    async def active_matches():
        return [{
            "set_id": "challonge:test:match", "provider_type": "challonge", "status": "called",
            "call_message_id": "7301", "discord_thread_id": "7201",
            "p1_discord": "100", "p2_discord": "200", "is_stream_match": 0,
        }]

    monkeypatch.setattr(match_threads, "get_active_matches", active_matches)
    bot = _RestoreBot()
    assert await match_threads.restore_ready_check_views(bot) == 1
    view, message_id = bot.views[0]
    assert message_id == 7301
    assert view.timeout is None
    assert view.ready_button.custom_id == "aitob:ready:challonge:test:match"


@pytest.mark.asyncio
async def test_ready_button_acknowledges_before_local_workflow(monkeypatch):
    """Discord's three-second interaction deadline cannot mask a saved Ready."""
    from backend.bot import match_threads
    from backend.core import match_commands

    events = []
    match = {
        "set_id": "challonge:test:match", "tournament_slug": "challonge:test",
        "status": "called", "hub_status": "called", "p1_ready": False, "p2_ready": False,
    }

    async def current(_set_id):
        return dict(match)

    class Service:
        async def mark_ready(self, set_id, player):
            assert events == ["deferred"]
            events.append(f"saved:{player}")

    class Response:
        async def defer(self, *, ephemeral, thinking):
            assert ephemeral is True and thinking is False
            events.append("deferred")
        async def send_message(self, *_args, **_kwargs):
            events.append("rejected")

    class Followup:
        async def send(self, *_args, **_kwargs):
            events.append("confirmed")

    class User:
        id = 100
        display_name = "Test player"

    class Interaction:
        user = User()
        response = Response()
        followup = Followup()

    monkeypatch.setattr(match_threads, "get_active_match", current)
    monkeypatch.setattr(match_threads, "_challonge_local_workflow_enabled", lambda: _true())
    monkeypatch.setattr(match_commands, "MatchCommandService", Service)
    view = match_threads.ReadyCheckView("challonge:test:match", "100", "200", False, _Thread(), _Bot())
    await view.ready_button.callback(Interaction())
    assert events == ["deferred", "saved:p1", "confirmed"]


async def _true():
    return True
