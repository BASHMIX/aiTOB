import pytest
from backend.core import database
from backend.core.tournament_setup import create_draft
from backend.core.tournament_readiness import compute_readiness


@pytest.mark.asyncio
async def test_grouped_readiness_has_precise_required_and_optional_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_DSN", str(tmp_path / "readiness.pg"))
    await database.init_db()
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces(id,slug,name) VALUES ('w','w','W')")
        await db.execute("INSERT INTO users(id,email,display_name,password_hash) VALUES ('u','u@example.com','U','x')")
        await db.commit()
    draft = await create_draft("w", "u")
    result = await compute_readiness(draft["id"], "w")
    assert result["state"] == "blocked"
    assert {item["step"] for item in result["checks"]} >= {"provider", "tournament", "discord", "assistant"}
    assert any(item["requirement"] == "optional" for item in result["checks"])
