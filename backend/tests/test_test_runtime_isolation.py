"""Guards against tests accidentally touching the operating SQLite file."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import socket

import pytest

from backend.core import database


def test_database_module_uses_the_explicit_pytest_database():
    configured = Path(os.environ["AITOB_TEST_DB_PATH"]).resolve()
    operating = Path(__file__).resolve().parents[2] / "backend" / "core" / "database.sqlite"
    assert Path(database.DB_PATH).resolve() == configured
    assert configured != operating.resolve()
    assert os.environ["AITOB_TESTING"] == "1"


def test_testing_mode_refuses_the_operating_database_fallback():
    env = os.environ.copy()
    env["AITOB_TESTING"] = "1"
    env.pop("DB_PATH", None)
    env.pop("AITOB_TEST_DB_PATH", None)
    result = subprocess.run(
        [sys.executable, "-c", "import backend.core.database"],
        cwd=Path(__file__).resolve().parents[2], env=env,
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "Tests require an explicit DB_PATH" in result.stderr


def test_external_network_is_blocked_unless_explicitly_enabled():
    if os.environ.get("AITOB_ALLOW_LIVE_TESTS", "false").lower() == "true":
        pytest.skip("Live-test opt-in intentionally permits external network")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(RuntimeError, match="External network is disabled"):
            sock.connect(("203.0.113.1", 443))


def test_no_test_fixture_uses_a_project_relative_sqlite_file():
    tests_root = Path(__file__).resolve().parent
    offenders = [
        path for path in tests_root.rglob("test_*.py")
        if path != Path(__file__) and "backend/core/test_" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
