from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_bot_on_ready_pause_does_not_attach_workers(monkeypatch):
    import backend.bot.main as bot_main

    monkeypatch.setenv("AITOB_DISABLE_BACKGROUND_WORKERS", "true")
    monkeypatch.setattr(bot_main, "init_db", _noop)
    monkeypatch.setattr(bot_main, "ready_message", lambda: "ready")

    started = []

    class RuntimeStub:
        def start(self, coroutine):
            started.append(coroutine)
            coroutine.close()

    monkeypatch.setattr(bot_main, "_runtime_tasks", RuntimeStub())
    await bot_main.on_ready()
    assert started == []


async def _noop():
    return None
