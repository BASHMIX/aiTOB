"""Guards against tests accidentally touching the operating PostgreSQL database."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import socket

import pytest

from backend.core import database


def test_database_module_uses_a_disposable_postgres_database():
    configured = os.environ["DATABASE_URL"]
    source = os.environ["AITOB_PG_TEST_URL"]
    assert database.DATABASE_DSN == configured
    assert configured.startswith(("postgresql://", "postgres://"))
    assert configured != source
    assert "/aitob_repo_test_" in configured
    assert os.environ["AITOB_TESTING"] == "1"


def test_missing_database_url_is_rejected():
    env = os.environ.copy()
    env["AITOB_TESTING"] = "1"
    env.pop("DATABASE_URL", None)
    env["AITOB_SKIP_ENV_FILES"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", "from backend.core.storage import require_runtime_database; require_runtime_database()"],
        cwd=Path(__file__).resolve().parents[2], env=env,
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "DATABASE_URL must be configured" in result.stderr


def test_external_network_is_blocked_unless_explicitly_enabled():
    if os.environ.get("AITOB_ALLOW_LIVE_TESTS", "false").lower() == "true":
        pytest.skip("Live-test opt-in intentionally permits external network")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(RuntimeError, match="External network is disabled"):
            sock.connect(("203.0.113.1", 443))
