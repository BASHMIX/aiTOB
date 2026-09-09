"""Process-wide pytest isolation, loaded before test modules import aiTOB."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
import shutil
import socket
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parent
OPERATING_DB = (PROJECT_ROOT / "backend" / "core" / "database.sqlite").resolve()
_created_test_dir: Path | None = None


def _configure_test_database() -> Path:
    global _created_test_dir
    configured = os.environ.get("AITOB_TEST_DB_PATH", "").strip()
    if configured:
        path = Path(configured).expanduser().resolve()
    else:
        _created_test_dir = Path(tempfile.mkdtemp(prefix="aitob-pytest-"))
        path = _created_test_dir / "backend-tests.sqlite"
    if path == OPERATING_DB:
        raise RuntimeError("Refusing to run tests against backend/core/database.sqlite; set AITOB_TEST_DB_PATH to a temporary file.")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Set both variables before any application module imports database.py.
    os.environ["AITOB_TESTING"] = "1"
    os.environ["AITOB_TEST_DB_PATH"] = str(path)
    os.environ["DB_PATH"] = str(path)
    # Never inherit a service DSN. PostgreSQL fixtures explicitly create a
    # disposable database later; an empty value also prevents dotenv fallback.
    os.environ["DATABASE_URL"] = ""
    os.environ.setdefault("AITOB_ALLOW_LIVE_TESTS", "false")
    return path


TEST_DB_PATH = _configure_test_database()


def _is_loopback(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    host = str(address[0]).lower()
    return host in {"127.0.0.1", "::1", "localhost"}


_socket_connect = socket.socket.connect
if os.environ["AITOB_ALLOW_LIVE_TESTS"].lower() != "true":
    def _deny_external_connect(sock: socket.socket, address: object):
        if _is_loopback(address):
            return _socket_connect(sock, address)
        raise RuntimeError("External network is disabled for local tests. Mark and run live tests with AITOB_ALLOW_LIVE_TESTS=true.")
    socket.socket.connect = _deny_external_connect


def pytest_configure(config):
    config.addinivalue_line("markers", "live_external: requires an explicitly enabled real external service")
    config.addinivalue_line(
        "markers",
        "sqlite_source_migration: migration test whose source is intentionally SQLite; target acceptance is tested separately",
    )


def pytest_collection_modifyitems(config, items):
    if os.environ["AITOB_ALLOW_LIVE_TESTS"].lower() == "true":
        return
    import pytest
    skip = pytest.mark.skip(reason="live external tests require AITOB_ALLOW_LIVE_TESTS=true")
    for item in items:
        if item.get_closest_marker("live_external"):
            item.add_marker(skip)
        if config.getoption("--postgres", default=False) and item.get_closest_marker("sqlite_source_migration"):
            item.add_marker(pytest.mark.skip(reason="SQLite source migration test; PostgreSQL target acceptance runs in test_postgres_migration.py"))


@atexit.register
def _cleanup_generated_database() -> None:
    if _created_test_dir:
        shutil.rmtree(_created_test_dir, ignore_errors=True)
