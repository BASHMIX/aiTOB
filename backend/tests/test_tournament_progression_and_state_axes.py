import pytest

from backend.core.tournament_progression import project_match


def test_four_axes_remain_independent_for_a_called_challonge_open_match():
    projection = project_match({
        "provider_type": "challonge", "provider_state_raw": "open",
        "provider_state_normalized": "not_started", "hub_status": "called",
        "sync_status": "local_only", "call_message_id": "msg-1", "thread_id": "thread-1",
        "called_at": "2026-09-05T12:00:00Z", "p1_name": "Alpha", "p2_name": "Bravo",
        "round_name": "Winners Round 1", "phase_group": "",
    })
    assert projection["state_axes"] == {
        "provider": {"raw": "open", "normalized": "not_started"},
        "hub_status": "called", "sync_status": "local_only",
    }
    assert projection["discord"]["call_sent"] is True
    assert projection["eligibility"]["two_sided"] is True


def test_conflict_does_not_replace_hub_in_progress_and_stale_revision_is_diagnostic():
    projection = project_match({
        "provider_type": "challonge", "provider_state_raw": "open", "provider_state_normalized": "not_started",
        "provider_revision": "9", "hub_status": "in_progress", "sync_status": "conflict",
        "p1_name": "Alpha", "p2_name": "Bravo", "round_name": "Losers Round 2",
    })
    assert projection["state_axes"]["hub_status"] == "in_progress"
    assert projection["state_axes"]["sync_status"] == "conflict"
    assert projection["provider_diagnostics"]["revision"] == "9"


def test_tbd_bye_and_pending_downstream_are_not_eligible_or_invented_as_ready():
    tbd = project_match({"provider_state_raw": "pending", "p1_name": "Alpha", "p2_name": "TBD", "round_name": "Round 2"})
    bye = project_match({"provider_state_raw": "bye", "p1_name": "Alpha", "p2_name": "TBD", "round_name": "Round 1"})
    assert tbd["eligibility"] == {"two_sided": False, "actionable": False, "reason": "Awaiting opponent"}
    assert bye["eligibility"] == {"two_sided": False, "actionable": False, "reason": "Provider marks this match as a bye or invalid"}


def test_legacy_startgg_response_has_no_empty_v2_axes_and_keeps_legacy_status():
    projection = project_match({"status": "called", "p1_name": "Alpha", "p2_name": "Bravo", "round_name": "Winners Semis"})
    assert projection["v2_available"] is False
    assert projection["legacy_status"] == "called"
    assert projection["state_axes"] is None


def test_legacy_challonge_row_without_v2_axes_still_projects_actions(monkeypatch):
    """A rolling migration must not turn the active-matches endpoint into a 500."""
    from backend.api.routers.matches import _action_projection

    monkeypatch.setenv("CHALLONGE_LOCAL_WORKFLOW_ENABLED", "true")
    actions = _action_projection({
        "provider_type": "challonge", "state_axes": None,
        "status": "in_progress", "eligibility": {"actionable": True},
    })

    assert actions and actions["call"]["kind"] == "local"


def test_active_legacy_stream_match_keeps_result_controls_when_hub_axis_is_stale(monkeypatch):
    """An on-stream legacy match must not lose score/DQ controls during V2 rollout."""
    from backend.api.routers.matches import _action_projection

    monkeypatch.setenv("CHALLONGE_LOCAL_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("CHALLONGE_SCORE_COMMANDS_ENABLED", "true")
    monkeypatch.setenv("CHALLONGE_DQ_COMMANDS_ENABLED", "true")
    actions = _action_projection({
        "provider_type": "challonge",
        "status": "in_progress",
        "state_axes": {"hub_status": "not_started"},
        "eligibility": {"actionable": True},
    })

    assert actions and actions["report_score"]["enabled"] is True
    assert actions["dq"]["enabled"] is True


def test_challonge_manual_dq_is_available_for_an_eligible_not_started_match(monkeypatch):
    from backend.api.routers.matches import _action_projection

    monkeypatch.setenv("CHALLONGE_LOCAL_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("CHALLONGE_DQ_COMMANDS_ENABLED", "true")
    actions = _action_projection({
        "provider_type": "challonge",
        "status": "not_started",
        "state_axes": {"hub_status": "not_started"},
        "eligibility": {"actionable": True},
    })

    assert actions and actions["dq"]["enabled"] is True


@pytest.mark.asyncio
async def test_active_match_display_is_sqlite_only_and_does_not_change_workflow(tmp_path, monkeypatch):
    """Repeated card reads serialize axes but never call a provider or mutate rows."""
    from backend.api.routers import matches
    from backend.core import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "progression.sqlite"))

    async def no_provider_call(*_args, **_kwargs):
        raise AssertionError("A display read must not resolve a provider")

    monkeypatch.setattr(matches, "get_provider_for_tournament", no_provider_call)
    await database.init_db()
    await database.upsert_active_match(
        "challonge:m1", tournament_slug="challonge:fnc:1", p1_name="Alpha", p2_name="Bravo",
        status="not_started", station_id="station_1", provider_state_raw="open",
        provider_state_normalized="not_started", hub_status="called", sync_status="local_only",
        call_message_id="discord-message", thread_id="discord-thread",
    )
    before = await database.get_active_match("challonge:m1")
    assert before["tournament_slug"] == "challonge:fnc:1"

    responses = [await matches.api_active_matches(tournament_slug="challonge:fnc:1", event_id=None) for _ in range(10)]

    payload = responses[-1].model_dump()["matches"][0]
    after = await database.get_active_match("challonge:m1")
    assert payload["state_axes"]["provider"] == {"raw": "open", "normalized": "not_started"}
    assert payload["state_axes"]["hub_status"] == "called"
    assert payload["discord"]["call_sent"] is True
    assert before == after  # includes status, station, and all persisted workflow fields
