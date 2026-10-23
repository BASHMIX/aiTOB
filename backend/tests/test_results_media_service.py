"""Tests for Results Media domain service orchestration and presentation freezing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from unittest.mock import AsyncMock, patch

from backend.core.contracts import (
    ProviderEventResults,
    ProviderPageMetadata,
    ProviderStandingEntry,
    ProviderSnapshotV2,
    ProviderSnapshotRequestV2,
    SnapshotScope,
)
from backend.core.results_media import (
    classify_readiness,
    compute_observation_hash,
    refresh_event_results,
    results_scene_page_size,
    validate_results_scene,
    validate_provider_event_results,
)
from backend.tests.results_media_test_support import valid_freeform_results_scene, valid_results_scene


def test_classify_readiness():
    """Verify Final, Provisional, and Stale readiness rules."""
    # Completed event observed recently -> final
    final_results = ProviderEventResults(
        event_id="ev-1",
        event_name="Tekken 8",
        is_completed=True,
        completion_state_raw="COMPLETED",
        standings=[ProviderStandingEntry(ordinal=1, placement=1, entrant_id="e-1", entrant_name="Player 1")],
    )
    assert classify_readiness(final_results, observed_seconds_ago=10) == "final"
    # Completed event observed long ago -> stale
    assert classify_readiness(final_results, observed_seconds_ago=7200) == "stale"

    # Incomplete event -> provisional
    provisional_results = ProviderEventResults(
        event_id="ev-2",
        event_name="SF6",
        is_completed=False,
        completion_state_raw="ACTIVE",
        standings=[ProviderStandingEntry(ordinal=1, placement=1, entrant_id="e-2", entrant_name="Player 2")],
    )
    assert classify_readiness(provisional_results, observed_seconds_ago=10) == "provisional"


def test_results_scene_page_size_uses_frozen_results_group():
    scene = valid_results_scene("version-page-size")
    scene["nodes"]["results-group"]["pageSize"] = 24
    assert results_scene_page_size(scene) == 24
    assert results_scene_page_size({"nodes": {}}) == 16


def test_freeform_result_card_scene_is_valid_for_live_playback():
    scene = valid_freeform_results_scene("version-freeform")
    assert validate_results_scene(
        scene,
        version_id="version-freeform",
        require_sequence=True,
    ) == []
    assert results_scene_page_size(scene) == 16

    # Explicitly linked cards use the Results Cards schedule even when the
    # one-card Auto Sequence generator is disabled.
    scene["nodes"]["cards"]["autoSequence"]["enabled"] = False
    assert validate_results_scene(
        scene,
        version_id="version-freeform",
        require_sequence=True,
    ) == []


def test_freeform_result_card_scene_rejects_runtime_generated_nodes():
    scene = valid_freeform_results_scene("version-freeform")
    scene["nodes"]["runtime-card"] = {
        **scene["nodes"]["stage"],
        "id": "runtime-card",
        "generated": True,
    }
    errors = validate_results_scene(scene, version_id="version-freeform", require_sequence=True)
    assert "scene_generated_instance_forbidden:runtime-card" in errors


def test_compute_observation_hash_deterministic():
    """Verify observation hash is deterministic and changes when presentation changes."""
    standings = [
        ProviderStandingEntry(ordinal=1, placement=1, entrant_id="e-1", entrant_name="Knee"),
        ProviderStandingEntry(ordinal=2, placement=2, entrant_id="e-2", entrant_name="Arslan"),
    ]
    presentations = {
        "e-1": {"display_name": {"value": "Knee", "source": "provider_snapshot"}},
        "e-2": {"display_name": {"value": "Arslan", "source": "provider_snapshot"}},
    }
    hash1 = compute_observation_hash("ev-1", standings, presentations)
    hash2 = compute_observation_hash("ev-1", standings, presentations)
    assert hash1 == hash2

    # Change in presentation alters the hash
    presentations_modified = {
        "e-1": {"display_name": {"value": "DRX | Knee", "source": "entrant_override"}},
        "e-2": {"display_name": {"value": "Arslan", "source": "provider_snapshot"}},
    }
    hash3 = compute_observation_hash("ev-1", standings, presentations_modified)
    assert hash1 != hash3

    provisional_hash = compute_observation_hash(
        "ev-1", standings, presentations, is_completed=False, completion_state_raw="ACTIVE"
    )
    final_hash = compute_observation_hash(
        "ev-1", standings, presentations, is_completed=True, completion_state_raw="COMPLETED"
    )
    assert provisional_hash != final_hash


@pytest.mark.parametrize(
    ("standings", "page", "expected_error"),
    [
        (
            [
                ProviderStandingEntry(ordinal=1, placement=1, entrant_id="dup", entrant_name="One"),
                ProviderStandingEntry(ordinal=2, placement=2, entrant_id="dup", entrant_name="Duplicate"),
            ],
            ProviderPageMetadata(number=1, size=2, total_entries=2, has_more=False, is_complete=True),
            "duplicate entrant identity",
        ),
        (
            [
                ProviderStandingEntry(ordinal=1, placement=2, entrant_id="a", entrant_name="A"),
                ProviderStandingEntry(ordinal=2, placement=1, entrant_id="b", entrant_name="B"),
            ],
            ProviderPageMetadata(number=1, size=2, total_entries=2, has_more=False, is_complete=True),
            "not monotonic",
        ),
        (
            [ProviderStandingEntry(ordinal=1, placement=1, entrant_id="a", entrant_name="A")],
            ProviderPageMetadata(number=1, size=1, total_entries=2, has_more=False, is_complete=True),
            "count does not match",
        ),
        (
            [ProviderStandingEntry(ordinal=1, placement=1, entrant_id="a", entrant_name="A")],
            ProviderPageMetadata(number=1, size=1, total_entries=2, has_more=True, is_complete=False),
            "pagination is incomplete",
        ),
    ],
)
def test_completed_provider_results_fail_closed_on_invalid_structure(standings, page, expected_error):
    results = ProviderEventResults(
        event_id="ev-validated",
        event_name="Validated Event",
        is_completed=True,
        completion_state_raw="COMPLETED",
        standings=standings,
        page=page,
    )

    errors = validate_provider_event_results(
        results,
        expected_event_id="ev-validated",
        provider_type="startgg",
    )

    assert any(expected_error in error for error in errors)


@pytest.mark.asyncio
async def test_refresh_orchestration_external_call_before_tx(postgres_repository_database):
    """Verify refresh performs provider query outside of database write transaction."""
    from backend.core import database
    ws_id = "ws-results-srv"
    user_id = "usr-srv-1"
    async with database.dbapi.connect(database.DATABASE_DSN) as db:
        await db.execute("INSERT INTO workspaces (id, name, slug) VALUES (?, ?, ?) ON CONFLICT DO NOTHING", (ws_id, "Test", "test"))
        await db.execute("INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'hash') ON CONFLICT DO NOTHING", (user_id, "u@test.com", "usrv"))
        await db.execute("INSERT INTO workspace_memberships (workspace_id, user_id, role) VALUES (?, ?, 'owner') ON CONFLICT DO NOTHING", (ws_id, user_id))
        await db.execute("INSERT INTO tournaments (workspace_id, slug, name, provider_type) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING", (ws_id, "tourney-t8", "Tourney T8", "startgg"))
        await db.commit()

    pool = None

    mock_provider = AsyncMock()
    mock_provider.provider_type = "startgg"
    mock_provider.fetch_snapshot.return_value = ProviderSnapshotV2(
        request=ProviderSnapshotRequestV2(
            provider_type="startgg",
            provider_account_id="acc-1",
            tournament_id="tourney-t8",
            scope=SnapshotScope.FINAL_STANDINGS,
        ),
        observed_at=datetime.now(UTC).isoformat(),
        payload={
            "event_results": ProviderEventResults(
                event_id="ev-100",
                event_name="Top 8 Final",
                game_name="Guilty Gear",
                is_completed=True,
                completion_state_raw="COMPLETED",
                standings=[
                    ProviderStandingEntry(ordinal=1, placement=1, entrant_id="e-1", entrant_name="Player 1"),
                    ProviderStandingEntry(ordinal=2, placement=2, entrant_id="e-2", entrant_name="Player 2"),
                ],
                page=ProviderPageMetadata(number=1, size=2, total_entries=2, has_more=False, is_complete=True),
            )
        },
    )

    with patch("backend.core.results_media.get_provider_for_tournament", return_value=mock_provider):
        # First call creates a new version
        res1 = await refresh_event_results(
            workspace_id=ws_id,
            tournament_slug="tourney-t8",
            event_id="ev-100",
            user_id=user_id,
            force=False,
        )
        assert res1["reused"] is False
        assert res1["version"]["capture_status"] == "final"
        assert res1["version"]["entry_count"] == 2

        # Second call with identical data reuses the existing version
        res2 = await refresh_event_results(
            workspace_id=ws_id,
            tournament_slug="tourney-t8",
            event_id="ev-100",
            user_id=user_id,
            force=False,
        )
        assert res2["reused"] is True
        assert res2["version"]["id"] == res1["version"]["id"]

        # A later successful verification must not leave identical standings
        # permanently stale merely because their content hash is unchanged.
        stale_observed_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        async with database.dbapi.connect(database.DATABASE_DSN) as db:
            await db.execute(
                "UPDATE tournament_result_versions SET observed_at=? WHERE id=?",
                (stale_observed_at, res1["version"]["id"]),
            )
            await db.commit()
        mock_provider.fetch_snapshot.return_value = ProviderSnapshotV2(
            request=mock_provider.fetch_snapshot.return_value.request,
            observed_at=datetime.now(UTC).isoformat(),
            payload=mock_provider.fetch_snapshot.return_value.payload,
        )
        res3 = await refresh_event_results(
            workspace_id=ws_id,
            tournament_slug="tourney-t8",
            event_id="ev-100",
            user_id=user_id,
            force=True,
        )
        assert res3["reused"] is False
        assert res3["version"]["id"] != res1["version"]["id"]
        assert res3["readiness_state"] == "final"

        # Identical placements transitioning from Active to Completed are a
        # new authoritative observation, not a reusable provisional row.
        transition_standings = [
            ProviderStandingEntry(
                ordinal=1, placement=1, entrant_id="transition-1", entrant_name="Winner"
            )
        ]
        transition_request = mock_provider.fetch_snapshot.return_value.request
        mock_provider.fetch_snapshot.return_value = ProviderSnapshotV2(
            request=transition_request,
            observed_at=datetime.now(UTC).isoformat(),
            payload={"event_results": ProviderEventResults(
                event_id="ev-transition",
                event_name="Transition Event",
                is_completed=False,
                completion_state_raw="ACTIVE",
                standings=transition_standings,
                page=ProviderPageMetadata(
                    number=1, size=1, total_entries=1, has_more=False, is_complete=True
                ),
            )},
        )
        provisional = await refresh_event_results(
            workspace_id=ws_id,
            tournament_slug="tourney-t8",
            event_id="ev-transition",
            user_id=user_id,
        )
        assert provisional["version"]["capture_status"] == "provisional"

        mock_provider.fetch_snapshot.return_value = ProviderSnapshotV2(
            request=transition_request,
            observed_at=datetime.now(UTC).isoformat(),
            payload={"event_results": ProviderEventResults(
                event_id="ev-transition",
                event_name="Transition Event",
                is_completed=True,
                completion_state_raw="COMPLETED",
                standings=transition_standings,
                page=ProviderPageMetadata(
                    number=1, size=1, total_entries=1, has_more=False, is_complete=True
                ),
            )},
        )
        final = await refresh_event_results(
            workspace_id=ws_id,
            tournament_slug="tourney-t8",
            event_id="ev-transition",
            user_id=user_id,
        )
        assert final["reused"] is False
        assert final["version"]["id"] != provisional["version"]["id"]
        assert final["version"]["capture_status"] == "final"
