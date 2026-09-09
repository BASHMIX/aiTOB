"""Runtime entrypoints never silently reopen the operating SQLite database."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core import storage


def test_runtime_database_gate_rejects_missing_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AITOB_TESTING", raising=False)
    monkeypatch.delenv("AITOB_SQLITE_MIGRATION_TOOL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        storage.require_runtime_database()


def test_invalid_url_never_falls_back_even_in_test_mode(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "invalid://configured")
    monkeypatch.setenv("AITOB_TESTING", "1")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        storage.connect(":memory:")


def test_sqlite_test_requires_an_explicit_path(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setenv("AITOB_TESTING", "1")
    with pytest.raises(RuntimeError, match="Explicit"):
        storage.connect()


@pytest.mark.asyncio
async def test_postgres_connection_failure_is_redacted_without_sqlite_fallback(monkeypatch):
    import psycopg
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:never-display-me@127.0.0.1/test")
    async def fail(*args, **kwargs):
        raise psycopg.OperationalError("never-display-me")
    monkeypatch.setattr(psycopg.AsyncConnection, "connect", fail)
    with pytest.raises(RuntimeError, match="PostgreSQL connection unavailable") as caught:
        async with storage.connect(":memory:"):
            pytest.fail("connection failure must prevent entry")
    assert "never-display-me" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_launcher_fails_before_starting_services_without_database_url(tmp_path: Path):
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env.pop("AITOB_TESTING", None)
    env.pop("AITOB_SQLITE_MIGRATION_TOOL", None)
    result = subprocess.run(
        [sys.executable, "run.py", "--no-frontend"],
        cwd=Path(__file__).resolve().parents[2], env=env,
        text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 2
    assert "DATABASE_URL is required" in result.stdout


def test_runtime_bot_paths_do_not_open_sqlite_directly():
    """T004 guard: bot/runtime code must use repository/storage boundaries."""
    root = Path(__file__).resolve().parents[2]
    for base in (root / "backend" / "bot",):
      for path in base.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "aiosqlite.connect(DB_PATH)" not in source, str(path)
        assert "from core.database import aiosqlite" not in source, str(path)


def test_workspace_api_paths_use_repository_boundary():
    """Tenant-facing player/admin checks must not bypass repository transport."""
    root = Path(__file__).resolve().parents[2]
    for path in (root / "backend" / "api" / "routers" / "players.py", root / "backend" / "api" / "auth.py"):
        source = path.read_text(encoding="utf-8")
        assert "aiosqlite.connect" not in source, str(path)


def test_all_runtime_modules_use_storage_adapter_not_sqlite_driver():
    """T004 guard: SQLite drivers are confined to the adapter and migration code."""
    import re

    root = Path(__file__).resolve().parents[2]
    allowed = {
        root / "backend" / "core" / "storage.py",
        root / "backend" / "core" / "database.py",
        root / "backend" / "core" / "schema_migrations.py",
    }
    direct_import = re.compile(r"^\s*(?:from|import)\s+(?:aiosqlite|sqlite3)(?:\s|$)", re.MULTILINE)
    for base in (root / "backend" / "api", root / "backend" / "bot", root / "backend" / "core"):
        for path in base.rglob("*.py"):
            if path in allowed or "tests" in path.parts:
                continue
            assert not direct_import.search(path.read_text(encoding="utf-8")), str(path)
