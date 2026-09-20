"""PostgreSQL-only asynchronous database transport for aiTOB."""
from __future__ import annotations

import os
import asyncio
import re
from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any

# psycopg async cannot run on Windows' Proactor loop. Configure this before the
# API/bot creates its event loop; Linux deployments keep their normal policy.
if os.name == "nt" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def is_postgres() -> bool:
    return os.getenv("DATABASE_URL", "").strip().lower().startswith(("postgres://", "postgresql://"))


RUNTIME_DATABASE_ERROR = (
    "DATABASE_URL must be configured with a PostgreSQL connection string."
)


def require_runtime_database() -> str:
    """Fail before a service begins accepting work without PostgreSQL."""
    dsn = os.getenv("DATABASE_URL", "").strip()
    if dsn and not is_postgres():
        raise RuntimeError("DATABASE_URL must select PostgreSQL; no fallback is allowed")
    if not is_postgres():
        raise RuntimeError(RUNTIME_DATABASE_ERROR)
    return dsn


def _bind_parameters(statement: str) -> str:
    """Translate bind markers only in executable SQL, never literals/comments."""
    out: list[str] = []
    i, state, dollar_tag = 0, "code", ""
    block_depth, escape_string = 0, False
    while i < len(statement):
        char = statement[i]
        next_char = statement[i + 1] if i + 1 < len(statement) else ""
        if state == "code":
            if char == "'":
                state = "single"
                escape_string = i > 0 and statement[i - 1] in "Ee" and (i < 2 or not (statement[i - 2].isalnum() or statement[i - 2] == "_"))
            elif char == '"': state = "double"
            elif char == "-" and next_char == "-": state = "line"
            elif char == "/" and next_char == "*":
                state, block_depth = "block", 1
                out.extend((char, next_char)); i += 2; continue
            elif char == "$":
                # PostgreSQL dollar-quoted bodies can contain bind-looking
                # text, quotes, and comments; none of it is executable SQL.
                match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", statement[i:])
                if match:
                    dollar_tag = match.group(0)
                    out.append(dollar_tag)
                    i += len(dollar_tag)
                    state = "dollar"
                    continue
            elif char == "?": out.append("%s"); i += 1; continue
            elif char == ":":
                if next_char == ":":
                    out.extend((char, next_char)); i += 2; continue
                match = re.match(r":([A-Za-z_][A-Za-z0-9_]*)", statement[i:])
                if match:
                    out.append(f"%({match.group(1)})s"); i += len(match.group(0)); continue
        elif state == "single" and escape_string and char == "\\":
            out.extend((char, next_char)); i += 2; continue
        elif state == "single" and char == "'":
            if next_char == "'": out.extend((char, next_char)); i += 2; continue
            state = "code"
        elif state == "double" and char == '"': state = "code"
        elif state == "line" and char == "\n": state = "code"
        elif state == "block" and char == "/" and next_char == "*":
            block_depth += 1
            out.extend((char, next_char)); i += 2; continue
        elif state == "block" and char == "*" and next_char == "/":
            block_depth -= 1
            out.extend((char, next_char)); i += 2
            if block_depth == 0: state = "code"
            continue
        elif state == "dollar" and statement.startswith(dollar_tag, i):
            out.append(dollar_tag)
            i += len(dollar_tag)
            dollar_tag = ""
            state = "code"
            continue
        out.append(char); i += 1
    return "".join(out)


def _query(statement: str, *, escape_percent: bool = False) -> str:
    value = statement.strip()
    # Repositories use qmark/named bind markers; values are always bound.
    return _bind_parameters(value.replace("%", "%%") if escape_percent else value)


class Row(dict):
    """Dictionary-style PostgreSQL row with numeric access for repositories."""
    def __init__(self, columns: list[str], values: tuple[Any, ...]):
        super().__init__(zip(columns, values))
        self._values = values

    def __getitem__(self, key: Any) -> Any:
        return self._values[key] if isinstance(key, int) else super().__getitem__(key)


class _Cursor:
    def __init__(self, raw: Any):
        self._raw = raw

    def _row(self, value: tuple[Any, ...] | None) -> Row | None:
        if value is None:
            return None
        columns = [item.name for item in self._raw.description or ()]
        return Row(columns, value)

    async def fetchone(self):
        return self._row(await self._raw.fetchone())

    async def fetchall(self):
        return [self._row(value) for value in await self._raw.fetchall()]

    @property
    def description(self):
        # A few legacy bot tools construct dictionaries from DB-API metadata.
        return tuple((item.name,) for item in self._raw.description or ())

    @property
    def rowcount(self):
        return self._raw.rowcount

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._raw.close()


class _Execute:
    def __init__(self, connection: "_Connection", statement: str, params: Iterable[Any] | None):
        self.connection = connection
        self.statement = statement
        self.params = params if isinstance(params, dict) else tuple(params or ())
        self.cursor = None

    async def _run(self) -> _Cursor:
        if self.cursor is None:
            raw = self.connection._raw.cursor()
            try:
                # PostgreSQL has no BEGIN mode. Start a normal
                # transaction and let each repository acquire its own
                # workspace/row-scoped lock before mutating data. A generic
                # advisory lock here would serialize unrelated Workspaces.
                await raw.execute(_query(self.statement, escape_percent=bool(self.params)), self.params or None)
            except BaseException:
                await raw.close()
                raise
            self.cursor = _Cursor(raw)
        return self.cursor

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self):
        return await self._run()

    async def __aexit__(self, exc_type, exc, tb):
        if self.cursor:
            await self.cursor.__aexit__(exc_type, exc, tb)


class _Connection:
    def __init__(self, dsn: str):
        self.dsn, self._raw, self.row_factory = dsn, None, None

    async def __aenter__(self):
        from psycopg import AsyncConnection, Error
        try:
            self._raw = await AsyncConnection.connect(self.dsn, connect_timeout=10)
        except (Error, ValueError):
            raise RuntimeError("PostgreSQL connection unavailable; service startup/work must stop") from None
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._raw:
            try:
                if exc_type:
                    await self._raw.rollback()
            finally:
                await self._raw.close()

    def execute(self, statement: str, params: Iterable[Any] | None = None) -> _Execute:
        return _Execute(self, statement, params)

    async def executemany(self, statement: str, params_seq: Iterable[Iterable[Any]]):
        raw = self._raw.cursor()
        try:
            await raw.executemany(_query(statement, escape_percent=True), params_seq)
        finally:
            await raw.close()

    async def commit(self):
        await self._raw.commit()

    async def rollback(self):
        await self._raw.rollback()


def connect(_target: str | None = None):
    """Create a PostgreSQL connection; the DSN always comes from DATABASE_URL."""
    return _Connection(require_runtime_database())


dbapi = SimpleNamespace(connect=connect, Row=Row, Connection=_Connection)
