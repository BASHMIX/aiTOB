from __future__ import annotations

import json
import asyncio

from backend.core.storage import dbapi as aiosqlite
import pytest

from backend.core import database
from backend.core.contracts import ProviderEntrant, ProviderSet, ProviderSetState


def _set(match_id: str, state: str = "open", revision: str = "2", p1: str = "p1", p2: str | None = "p2") -> ProviderSet:
    normalized = {
        "pending": ProviderSetState.NOT_STARTED, "open": ProviderSetState.NOT_STARTED,
        "complete": ProviderSetState.COMPLETE, "bye": ProviderSetState.INVALID,
    }[state]
    return ProviderSet(
        id=f"challonge:fnc-jo:18449397:{match_id}", provider_set_id=match_id,
        state=normalized, provider_state_raw=state, provider_revision=revision,
        provider_updated_at="2026-09-05T10:00:00Z", round_name="Round 1",
        entrant1=ProviderEntrant(p1, "Alpha"), entrant2=ProviderEntrant(p2, "Bravo") if p2 else None,
        event_id="18449397", event_name="Bracket",
    )


@pytest.fixture
async def challonge_db(tmp_path, monkeypatch):
    path = tmp_path / "snapshot.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    await database.init_db()
    await database.upsert_tournament(
        "challonge:account:fnc-jo:18449397", "FNC", None, None, None, json.dumps({}),
        provider_type="challonge", provider_tournament_id="18449397",
        provider_subdomain="fnc-jo", provider_account_id="account",
    )
    return path


@pytest.mark.asyncio
async def test_complete_snapshot_atomically_projects_open_complete_bye_and_tbd(challonge_db):
    slug = "challonge:account:fnc-jo:18449397"
    result = await database.apply_challonge_snapshot(
        slug, "account", [_set("open", "open"), _set("complete", "complete"), _set("bye", "bye", p2=None)],
        [ProviderEntrant("p1", "Alpha"), ProviderEntrant("p2", "Bravo")],
        scope="full_snapshot", revision="2", observed_at="2026-09-05T10:00:00Z",
        covered_scopes={"full_snapshot", "participants", "active_matches"}, complete_pages=True,
    )

    assert len(result["sets"]) == 3
    async with aiosqlite.connect(challonge_db) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM active_matches ORDER BY provider_set_id") as cursor:
            rows = [dict(row) for row in await cursor.fetchall()]
        async with db.execute("SELECT COUNT(*) FROM provider_snapshot_participants") as cursor:
            participant_count = (await cursor.fetchone())[0]
    assert [row["provider_state_raw"] for row in rows] == ["bye", "complete", "open"]
    assert rows[-1]["hub_status"] == "not_started"
    assert rows[-1]["status"] == "not_started"
    assert rows[0]["p2_name"] == "TBD"
    assert participant_count == 2


@pytest.mark.asyncio
async def test_failed_partial_pages_publish_nothing_and_preserve_last_healthy_snapshot(challonge_db):
    slug = "challonge:account:fnc-jo:18449397"
    with pytest.raises(ValueError):
        await database.apply_challonge_snapshot(
            slug, "account", [_set("open")], [], scope="full_snapshot", revision="2",
            observed_at=None, covered_scopes=set(), complete_pages=False,
        )

    assert await database.get_bracket_snapshot(slug) == {"sets": [], "synced_at": None}
    async with aiosqlite.connect(challonge_db) as db:
        async with db.execute("SELECT COUNT(*) FROM active_matches") as cursor:
            assert (await cursor.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_partial_scope_never_deletes_other_rows_and_snapshot_never_changes_station_or_legacy_live(challonge_db):
    slug = "challonge:account:fnc-jo:18449397"
    await database.apply_challonge_snapshot(
        slug, "account", [_set("m1"), _set("m2")], [], scope="full_snapshot", revision="2",
        observed_at=None, covered_scopes={"full_snapshot"}, complete_pages=True,
    )
    async with aiosqlite.connect(challonge_db) as db:
        await db.execute("INSERT INTO stations (id, name) VALUES ('station_x', 'Protected station')")
        await db.execute("""UPDATE active_matches SET status='in_progress', hub_status=NULL,
            station_id='station_x', is_stream_match=TRUE WHERE provider_set_id='m1'""")
        await db.commit()

    await database.apply_challonge_snapshot(
        slug, "account", [_set("m1", "open", revision="3", p1="p3")], [], scope="single_match",
        revision="3", observed_at=None, covered_scopes={"single_match"}, complete_pages=True,
    )
    async with aiosqlite.connect(challonge_db) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT provider_set_id, status, station_id, is_stream_match, p1_entrant_id FROM active_matches ORDER BY provider_set_id") as cursor:
            rows = [dict(row) for row in await cursor.fetchall()]
    assert [row["provider_set_id"] for row in rows] == ["m1", "m2"]
    assert rows[0]["status"] == "in_progress" and rows[0]["station_id"] == "station_x"
    assert rows[0]["is_stream_match"] == 1 and rows[0]["p1_entrant_id"] == "p3"


@pytest.mark.asyncio
async def test_stale_revision_cannot_replace_newer_projection(challonge_db):
    slug = "challonge:account:fnc-jo:18449397"
    await database.apply_challonge_snapshot(slug, "account", [_set("m1", revision="9")], [], scope="full_snapshot", revision="9", observed_at=None, covered_scopes={"full_snapshot"}, complete_pages=True)

    with pytest.raises(database.StaleProviderSnapshotError):
        await database.apply_challonge_snapshot(slug, "account", [_set("m1", "complete", revision="8")], [], scope="full_snapshot", revision="8", observed_at=None, covered_scopes={"full_snapshot"}, complete_pages=True)


@pytest.mark.asyncio
async def test_concurrent_snapshots_cannot_regress_revision(challonge_db):
    slug = "challonge:account:fnc-jo:18449397"
    async def publish(revision):
        return await database.apply_challonge_snapshot(
            slug, "account", [_set("race", revision=str(revision))], [],
            scope="full_snapshot", revision=str(revision), observed_at=None,
            covered_scopes={"full_snapshot"}, complete_pages=True,
        )
    outcomes = await asyncio.gather(*(publish(revision) for revision in (8, 3, 9, 4, 6)), return_exceptions=True)
    assert all(not isinstance(value, Exception) or isinstance(value, database.StaleProviderSnapshotError) for value in outcomes)
    async with aiosqlite.connect(challonge_db) as db:
        row = await (await db.execute("SELECT provider_revision FROM active_matches WHERE provider_set_id='race'")).fetchone()
    assert row[0] == "9"
