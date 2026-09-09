"""Server error telemetry is durable, bounded and redacted."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import backend.core.database as database
from backend.core.storage import dbapi as aiosqlite


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def error_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "errors.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    run(database.init_db())
    return path


def test_error_event_is_redacted_and_bounded(error_db: Path):
    async def verify():
        event_id = await database.record_error_event(
            method="POST",
            path="/api/integrations/test",
            exception_type="ProviderError",
            trace_id="trace-123",
            detail={
                "provider": "challonge",
                "Authorization": "Bearer never-store-this",
                "password": "also-never-store-this",
                "message": "request failed token=embedded-secret",
            },
        )
        async with aiosqlite.connect(error_db) as db:
            row = await (await db.execute(
                "SELECT method, path, exception_type, trace_id, detail_json "
                "FROM error_events WHERE id=?", (event_id,),
        )).fetchone()
        assert row is not None
        values = (
            (row["method"], row["path"], row["exception_type"], row["trace_id"], row["detail_json"])
            if isinstance(row, dict) else row
        )
        assert values[0:4] == ("POST", "/api/integrations/test", "ProviderError", "trace-123")
        detail = json.loads(values[4])
        assert detail["provider"] == "challonge"
        assert detail["Authorization"] == "[REDACTED]"
        assert detail["password"] == "[REDACTED]"
        assert "embedded-secret" not in values[4]
        assert len(values[4]) <= 4000

    run(verify())


def test_error_telemetry_failure_does_not_replace_original_failure(error_db: Path, monkeypatch: pytest.MonkeyPatch):
    class FailedConnection:
        async def __aenter__(self):
            raise RuntimeError("database unavailable")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def verify():
        monkeypatch.setattr(database.aiosqlite, "connect", lambda *args, **kwargs: FailedConnection())
        assert await database.record_error_event(
            method="GET", path="/boom", exception_type="RuntimeError"
        ) is None

    run(verify())
