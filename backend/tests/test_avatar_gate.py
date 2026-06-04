"""Tests for the broadcast-avatar soft gate.

Covers two critical paths added alongside the bio-code (Path B) avatar flow:

  • get_verified_players_missing_avatar() — backs the Hub AI reminder tool;
    must include verified players with no avatar (NULL or empty) and exclude
    everyone else (has-avatar, or not-yet-verified).
  • _map_discord_locale() — replaces Path A's language DM by deriving the
    player's language from Discord's native interaction locale.
"""
import os
import pytest

from backend.core.database import (
    init_db, create_or_update_player, get_verified_players_missing_avatar,
)

# Distinct file so it never collides with other suites' test DBs.
TEST_DB_PATH = "backend/core/test_avatar_gate.sqlite"


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


# ── get_verified_players_missing_avatar ─────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_avatar_includes_verified_without_avatar(setup_test_db):
    # NULL avatar (field never set) and empty-string avatar both count as "missing".
    await create_or_update_player(
        "u_no_avatar", startgg_id="100", gamer_tag="NoAv",
        is_verified=True, preferred_language="ar",
    )
    await create_or_update_player(
        "u_empty_avatar", startgg_id="101", gamer_tag="EmptyAv",
        is_verified=True, avatar_path="",
    )

    rows = await get_verified_players_missing_avatar()
    by_id = {r["discord_id"]: r for r in rows}

    assert "u_no_avatar" in by_id
    assert "u_empty_avatar" in by_id
    # The fields the reminder tool relies on come back intact.
    assert by_id["u_no_avatar"]["startgg_id"] == "100"
    assert by_id["u_no_avatar"]["preferred_language"] == "ar"
    assert by_id["u_no_avatar"]["gamer_tag"] == "NoAv"


@pytest.mark.asyncio
async def test_missing_avatar_excludes_verified_with_avatar(setup_test_db):
    await create_or_update_player(
        "u_has_avatar", startgg_id="200", is_verified=True,
        avatar_path="backend/api/static/avatars/200.jpg",
    )
    rows = await get_verified_players_missing_avatar()
    assert "u_has_avatar" not in {r["discord_id"] for r in rows}


@pytest.mark.asyncio
async def test_missing_avatar_excludes_unverified(setup_test_db):
    # Explicitly unverified, and a row that only relies on the column default —
    # both must be excluded since they haven't completed verification.
    await create_or_update_player("u_unverified", startgg_id="300", is_verified=False)
    await create_or_update_player("u_default_unverified", startgg_id="301")

    rows = await get_verified_players_missing_avatar()
    ids = {r["discord_id"] for r in rows}
    assert "u_unverified" not in ids
    assert "u_default_unverified" not in ids


@pytest.mark.asyncio
async def test_missing_avatar_empty_when_no_players(setup_test_db):
    assert await get_verified_players_missing_avatar() == []


# ── _map_discord_locale ─────────────────────────────────────────────────────
# Imported lazily inside each test so the (heavy) bot.main import isn't required
# to collect/run the DB tests above.

def test_map_discord_locale_arabic():
    from backend.bot.main import _map_discord_locale
    assert _map_discord_locale("ar") == "ar"
    assert _map_discord_locale("ar-SA") == "ar"
    assert _map_discord_locale("AR") == "ar"  # case-insensitive


def test_map_discord_locale_english_and_other_languages_default_to_en():
    from backend.bot.main import _map_discord_locale
    assert _map_discord_locale("en-US") == "en"
    assert _map_discord_locale("en-GB") == "en"
    assert _map_discord_locale("fr") == "en"
    assert _map_discord_locale("de") == "en"
    assert _map_discord_locale("ja") == "en"


def test_map_discord_locale_none_and_empty_default_to_en():
    from backend.bot.main import _map_discord_locale
    assert _map_discord_locale(None) == "en"
    assert _map_discord_locale("") == "en"
