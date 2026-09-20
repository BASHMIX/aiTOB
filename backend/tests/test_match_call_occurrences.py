import asyncio
import pytest

from backend.core import database
from backend.core.match_commands import record_called_occurrence


@pytest.mark.asyncio
async def test_provider_and_dashboard_called_observations_share_one_occurrence(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "calls.pg"))
    await database.init_db()
    first, second = await asyncio.gather(
        record_called_occurrence("w1", "t1", "m1", "v1", source="provider_sync"),
        record_called_occurrence("w1", "t1", "m1", "v1", source="dashboard"),
    )
    assert first["id"] == second["id"]
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        count = await (await db.execute("SELECT COUNT(*) FROM match_call_occurrences")).fetchone()
        outbox = await (await db.execute("SELECT COUNT(*) FROM workflow_outbox WHERE event_type='discord_call'")).fetchone()
    assert count[0] == 1
    assert outbox[0] == 1
    assert first["source_first_observed"] in {"provider_sync", "dashboard"}
