"""Audit records must retain operational evidence without retaining secrets."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import backend.core.database as database
from backend.core.storage import dbapi


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def audit_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "audit.pg"
    monkeypatch.setattr(database, "DATABASE_DSN", str(path))
    run(database.init_db())
    return path


def test_audit_detail_redacts_nested_secret_aliases_and_preserves_safe_metadata(audit_db: Path):
    """New secret-shaped keys must not leak merely because their name is an alias.

    Provider and mail integrations commonly call secrets ``clientSecret`` or
    put credentials under an HTTP ``headers`` object.  The audit trail must
    retain the fact an operation occurred without retaining either value.
    """
    async def verify():
        # PostgreSQL enforces the workspace ownership foreign key that PostgreSQL
        # development fixtures may not enforce; make the evidence valid on
        # both transports.
        async with dbapi.connect(database.DATABASE_DSN) as db:
            await db.execute(
                "INSERT INTO workspaces (id, slug, name) VALUES (?, ?, ?)",
                ("workspace-a", "workspace-a", "Audit workspace"),
            )
            await db.commit()
        event_id = await database.record_audit_event(
            workspace_id="workspace-a",
            action="integration.connection_test",
            outcome="failed",
            detail={
                "provider": "challonge",
                "clientSecret": "must-never-be-stored",
                "nested": {
                    "headers": {"X-Api-Key": "also-secret", "Accept": "application/json"},
                    "webhook_signing_key": "never-store-this",
                    "message": "provider returned Authorization: Bearer message-secret",
                },
            },
        )
        async with dbapi.connect(audit_db) as db:
            row = await (await db.execute(
                "SELECT detail_json FROM audit_events WHERE id=?", (event_id,),
            )).fetchone()
        assert row is not None
        detail = json.loads(row[0])
        assert detail["provider"] == "challonge"
        assert "message-secret" not in detail["nested"]["message"]
        assert "[REDACTED]" in detail["nested"]["message"]
        assert detail["clientSecret"] == "[REDACTED]"
        assert detail["nested"]["headers"] == "[REDACTED]"
        assert detail["nested"]["webhook_signing_key"] == "[REDACTED]"
        serialized = row[0]
        assert "must-never-be-stored" not in serialized
        assert "also-secret" not in serialized
        assert "never-store-this" not in serialized
        assert "message-secret" not in serialized

    run(verify())
