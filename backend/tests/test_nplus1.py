import pytest
import os
import aiosqlite
import time

from backend.core.database import (
    init_db,
    upsert_active_match,
    DB_PATH
)
from backend.api.routers.matches import api_get_conflicts

TEST_DB_PATH = "backend/core/test_database.sqlite"

@pytest.fixture
async def setup_test_db():
    import backend.core.database
    import backend.core.match_state

    orig_db_path = backend.core.database.DB_PATH
    backend.core.database.DB_PATH = TEST_DB_PATH
    backend.core.match_state.DB_PATH = TEST_DB_PATH

    await init_db()

    yield

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    backend.core.database.DB_PATH = orig_db_path
    backend.core.match_state.DB_PATH = orig_db_path

@pytest.mark.asyncio
async def test_conflicts_nplus1(setup_test_db):
    import backend.core.database

    async with aiosqlite.connect(TEST_DB_PATH) as db:
        # insert a bunch of conflicts
        for i in range(1000):
            set_id = f"set_{i}"
            await db.execute("""
                INSERT INTO conflicts (id, set_id, created_at, p1_claim, p2_claim)
                VALUES (?, ?, ?, ?, ?)
            """, (i, set_id, "2024-01-01", "1-0", "0-1"))
            await db.commit()

            await upsert_active_match(
                set_id=set_id,
                p1_name=f"Player 1 {i}",
                p2_name=f"Player 2 {i}",
                p1_entrant_id=f"e1_{i}",
                p2_entrant_id=f"e2_{i}"
            )

    start = time.time()
    resp = await api_get_conflicts()
    end = time.time()

    print(f"\nTime taken for 1000 conflicts: {end - start:.4f}s")
    assert len(resp.conflicts) == 1000
    assert resp.conflicts[0]["p1_name"] == "Player 1 0"
