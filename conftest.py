"""Process-wide pytest safety policy, loaded before application imports."""

from __future__ import annotations

import os
import socket


os.environ["AITOB_TESTING"] = "1"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
# Tests never inherit a service database. The repository fixture creates a
# dedicated PostgreSQL database and injects its DSN before each test runs.
os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("AITOB_ALLOW_LIVE_TESTS", "false")


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
        raise RuntimeError(
            "External network is disabled for local tests. Mark and run live "
            "tests with AITOB_ALLOW_LIVE_TESTS=true."
        )

    socket.socket.connect = _deny_external_connect


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live_external: requires an explicitly enabled real external service"
    )


def pytest_collection_modifyitems(config, items):
    if os.environ["AITOB_ALLOW_LIVE_TESTS"].lower() == "true":
        return
    import pytest

    skip = pytest.mark.skip(
        reason="live external tests require AITOB_ALLOW_LIVE_TESTS=true"
    )
    for item in items:
        if item.get_closest_marker("live_external"):
            item.add_marker(skip)
