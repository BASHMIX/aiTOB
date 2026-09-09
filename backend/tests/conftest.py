from pathlib import Path
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

# The repository-root conftest has already selected DB_PATH before this import.
from backend.core import database


def pytest_addoption(parser):
    parser.addoption("--postgres", action="store_true", help="Run selected repository tests in independent PostgreSQL databases")


@pytest.fixture(autouse=True)
def postgres_repository_database(request, monkeypatch):
    if not request.config.getoption("--postgres"):
        yield
        return
    import psycopg
    from psycopg import sql
    source = os.getenv("AITOB_PG_TEST_URL", "")
    if not source:
        pytest.fail("--postgres requires AITOB_PG_TEST_URL; no application DATABASE_URL is used")
    parts = urlsplit(source)
    name = "aitob_repo_test_" + uuid.uuid4().hex
    admin = urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, ""))
    target = urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, ""))
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    monkeypatch.setenv("DATABASE_URL", target)
    try:
        yield
    finally:
        with psycopg.connect(admin, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))

@pytest.fixture(autouse=True)
def assert_isolated_database():
    test_path = Path(database.DB_PATH).resolve()
    assert test_path != (Path(__file__).resolve().parents[2] / "backend" / "core" / "database.sqlite").resolve()
