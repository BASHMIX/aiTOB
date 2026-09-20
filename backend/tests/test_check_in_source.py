"""Tests for the per-tournament `check_in_source` setting (Dual-Mode Check-in, Commit 1).

Covers the foundation: the column defaults to 'discord', and update_tournament_settings
(the path the PATCH /tournaments/{slug}/settings route drives) persists 'startgg'.
"""
import os
import pytest

from backend.core.database import (
    init_db, upsert_tournament, get_tournament, update_tournament_settings,
)

TEST_DATABASE_DSN = ""
SLUG = "tournament/dualmode"


@pytest.fixture
async def setup_test_db(tmp_path):
    import backend.core.database
    import backend.core.match_state

    global TEST_DATABASE_DSN
    TEST_DATABASE_DSN = str(tmp_path / "check-in-source.pg")
    orig = backend.core.database.DATABASE_DSN
    backend.core.database.DATABASE_DSN = TEST_DATABASE_DSN
    backend.core.match_state.DATABASE_DSN = TEST_DATABASE_DSN
    await init_db()
    yield
    backend.core.database.DATABASE_DSN = orig
    backend.core.match_state.DATABASE_DSN = orig


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


@pytest.mark.asyncio
async def test_tournament_accent_colour_persists_across_a_database_read(setup_test_db):
    await upsert_tournament(SLUG, "Dual Mode", "", "", "", "{}")
    await update_tournament_settings(SLUG, accent_color="#0EA5E9")

    tournament = await get_tournament(SLUG)
    assert tournament["accent_color"] == "#0EA5E9"
