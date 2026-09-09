"""Phase 9B dry run must not touch Start.gg, stations, or real data."""
from __future__ import annotations

import json
import pytest

from backend.core import database
from backend.core.storage import dbapi as aiosqlite


@pytest.fixture
async def repair_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "repair.sqlite"))
    await database.init_db()
    await database.upsert_tournament("challonge:repair", "Repair", None, None, None, json.dumps({}), provider_type="challonge", provider_tournament_id="1")
    await database.upsert_tournament("startgg:protected", "Protected", None, None, None, json.dumps({}))
    await database.upsert_active_match("challonge:eligible", tournament_slug="challonge:repair", status="in_progress", provider_state_raw="open")
    await database.upsert_active_match("challonge:called", tournament_slug="challonge:repair", status="in_progress", provider_state_raw="open", called_at="2026-09-01T00:00:00+00:00")
    await database.upsert_active_match("challonge:station", tournament_slug="challonge:repair", status="in_progress", provider_state_raw="open", station_id="station-a")
    await database.upsert_active_match("challonge:closed", tournament_slug="challonge:repair", status="in_progress", provider_state_raw="complete")
    await database.upsert_active_match("startgg:testfnc", tournament_slug="startgg:protected", status="in_progress", station_id="station-a")
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO stations (id, name, active_match_id) VALUES ('station-a', 'Protected', 'startgg:testfnc')")
        await db.commit()


@pytest.mark.asyncio
async def test_dry_run_reports_only_eligible_challonge_false_live_rows(repair_db):
    from backend.core.challonge_state_repair import dry_run
    report = await dry_run(snapshot_id="snapshot-42", snapshot_observed_at="2026-09-05T10:00:00+00:00", provider_states={
        "challonge:eligible": {"raw": "open", "normalized": "not_started"},
        "challonge:called": {"raw": "open", "normalized": "not_started"},
        "challonge:station": {"raw": "open", "normalized": "not_started"},
        "challonge:closed": {"raw": "complete", "normalized": "complete"},
    })
    by_key = {row["match_key"]: row for row in report.rows}
    assert by_key["challonge:eligible"]["eligibility"] == "eligible"
    assert by_key["challonge:eligible"]["proposed_change"] == "not_started"
    assert by_key["challonge:called"]["eligibility"] == "excluded"
    assert by_key["challonge:station"]["eligibility"] == "excluded"
    assert by_key["challonge:closed"]["eligibility"] == "excluded"
    assert "startgg:testfnc" not in by_key
    assert (await database.get_active_match("challonge:eligible"))["status"] == "in_progress"
    assert (await database.get_active_match("startgg:testfnc"))["station_id"] == "station-a"


@pytest.mark.asyncio
async def test_apply_requires_exact_report_fingerprint_and_never_changes_startgg_or_station(repair_db):
    from backend.core.challonge_state_repair import apply_approved, dry_run
    report = await dry_run(snapshot_id="snapshot-42", snapshot_observed_at="2026-09-05T10:00:00+00:00", provider_states={
        "challonge:eligible": {"raw": "open", "normalized": "not_started"},
        "challonge:called": {"raw": "open", "normalized": "not_started"},
        "challonge:station": {"raw": "open", "normalized": "not_started"},
        "challonge:closed": {"raw": "complete", "normalized": "complete"},
    })
    with pytest.raises(ValueError, match="report changed"):
        await database.apply_challonge_state_repair_v2(report.report_id, "wrong", ["challonge:eligible"], applied_by="organizer")
    assert await apply_approved(report, ["challonge:eligible"], organizer="organizer") == 1
    repaired = await database.get_active_match("challonge:eligible")
    assert repaired["status"] == "not_started"
    assert repaired["provider_state_raw"] == "open"
    assert repaired["provider_state_normalized"] == "not_started"
    assert (await database.get_active_match("startgg:testfnc"))["station_id"] == "station-a"
    # A second application cannot alter or re-audit an already repaired row.
    assert await apply_approved(report, ["challonge:eligible"], organizer="organizer") == 0
    async with aiosqlite.connect(database.DB_PATH) as db:
        async with db.execute(
            "SELECT before_hub_status, after_hub_status FROM provider_reconciliation_audit "
            "WHERE set_id='challonge:eligible' AND action='state_repair_apply'"
        ) as cursor:
            audit_rows = await cursor.fetchall()
    assert [
        (row["before_hub_status"], row["after_hub_status"]) if isinstance(row, dict) else tuple(row)
        for row in audit_rows
    ] == [("in_progress", "not_started")]
