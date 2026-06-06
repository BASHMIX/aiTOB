"""Tests for the per-tournament `check_in_source` setting (Dual-Mode Check-in, Commit 1).

Covers the foundation: the column defaults to 'discord', and update_tournament_settings
(the path the PATCH /tournaments/{slug}/settings route drives) persists 'startgg'.
"""
import os
import pytest

from backend.core.database import (
    init_db, upsert_tournament, get_tournament, update_tournament_settings,
)

TEST_DB_PATH = "backend/core/test_check_in_source.sqlite"
SLUG = "tournament/dualmode"


@pytest.fixture
async def setup_test_db():
    import backend.core.database
    import backend.core.match_state

    orig = backend.core.database.DB_PATH
    backend.core.database.DB_PATH = TEST_DB_PATH
    backend.core.match_state.DB_PATH = TEST_DB_PATH
    await init_db()
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    backend.core.database.DB_PATH = orig
    backend.core.match_state.DB_PATH = orig


@pytest.mark.asyncio
async def test_check_in_source_defaults_to_discord(setup_test_db):
    await upsert_tournament(SLUG, "Dual Mode", "", "", "", "{}")
    t = await get_tournament(SLUG)
    assert t["check_in_source"] == "discord"


@pytest.mark.asyncio
async def test_check_in_source_persists_startgg(setup_test_db):
    await upsert_tournament(SLUG, "Dual Mode", "", "", "", "{}")
    await update_tournament_settings(SLUG, check_in_source="startgg")
    t = await get_tournament(SLUG)
    assert t["check_in_source"] == "startgg"


@pytest.mark.asyncio
async def test_check_in_source_can_revert_to_discord(setup_test_db):
    await upsert_tournament(SLUG, "Dual Mode", "", "", "", "{}")
    await update_tournament_settings(SLUG, check_in_source="startgg")
    await update_tournament_settings(SLUG, check_in_source="discord")
    t = await get_tournament(SLUG)
    assert t["check_in_source"] == "discord"
