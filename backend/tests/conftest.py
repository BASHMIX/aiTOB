from __future__ import annotations

import os
import asyncio
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

from backend.core import database


def pytest_addoption(parser):
    # Retained as a no-op compatibility flag for existing CI commands. All
    # repository tests now use PostgreSQL unconditionally.
    parser.addoption(
        "--postgres",
        action="store_true",
        default=True,
        help="Compatibility flag; PostgreSQL is always used",
    )


@pytest.fixture(scope="session")
def postgres_template_database():
    """Build the schema once; individual tests clone this clean template."""
    import psycopg
    from psycopg import sql

    source = os.getenv("AITOB_PG_TEST_URL", "").strip()
    if not source:
        pytest.fail(
            "PostgreSQL tests require AITOB_PG_TEST_URL pointing at a disposable "
            "server; application DATABASE_URL is never reused"
        )

    parts = urlsplit(source)
    name = "aitob_repo_template_" + uuid.uuid4().hex
    admin = urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, ""))
    target = urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, ""))
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    previous_url = os.environ.get("DATABASE_URL")
    previous_dsn = database.DATABASE_DSN
    os.environ["DATABASE_URL"] = target
    database.DATABASE_DSN = target
    try:
        asyncio.run(database.init_db())
        yield source, admin, name
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        database.DATABASE_DSN = previous_dsn
        with psycopg.connect(admin, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture(autouse=True)
def postgres_repository_database(monkeypatch, postgres_template_database):
    """Give every test an independent clone of the clean PostgreSQL schema."""
    import psycopg
    from psycopg import sql

    _source, admin, template_name = postgres_template_database
    name = "aitob_repo_test_" + uuid.uuid4().hex
    parts = urlsplit(admin)
    target = urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, ""))
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {} WITH TEMPLATE {}").format(
                sql.Identifier(name), sql.Identifier(template_name)
            )
        )
    monkeypatch.setenv("DATABASE_URL", target)
    monkeypatch.setattr(database, "DATABASE_DSN", target)
    try:
        yield target
    finally:
        with psycopg.connect(admin, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )
