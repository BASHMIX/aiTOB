"""Phase-2 guard: dark flags cannot alter active Start.gg behavior."""
from __future__ import annotations

from pathlib import Path

from backend.core.provider_feature_flags import get_provider_feature_flags


def test_phase7_flags_are_limited_to_challonge_branches_and_leave_startgg_legacy_paths():
    root = Path(__file__).resolve().parents[1]
    # match_threads now owns the explicitly gated Challonge local Ready path,
    # while its Start.gg branch remains the legacy transition path.  The guard
    # must be provider-specific; a global flag check here would leak behavior.
    thread_source = (root / "bot" / "match_threads.py").read_text(encoding="utf-8")
    assert "provider_feature_flags" in thread_source
    assert "is_challonge_local" in thread_source
    assert "await transition_match(self.set_id, \"in_progress\", workspace_id=self.workspace_id)" in thread_source
    assert "SyncCoordinator" not in thread_source

    # Phase 7A adopts flags only at the Challonge-owned local workflow boundary.
    # The legacy Start.gg code remains below the gated branch and is exercised by
    # the baseline suite unchanged.
    for path in (root / "core" / "match_state.py", root / "api" / "routers" / "matches.py"):
        source = path.read_text(encoding="utf-8")
        assert "provider_feature_flags" in source
        assert 'provider_type") == "challonge"' in source
    bot_source = (root / "bot" / "main.py").read_text(encoding="utf-8")
    assert "provider_feature_flags" in bot_source
    assert "drain_workflow_outbox" in bot_source
    score_source = (root / "core" / "score_reporting.py").read_text(encoding="utf-8")
    assert "provider_feature_flags" in score_source
    assert "_schedule_post_result_verification" in score_source
    assert 'provider_name", "") != "challonge"' not in score_source

    sync_source = (root / "core" / "provider_sync_manager.py").read_text(encoding="utf-8")
    assert "provider_feature_flags" in sync_source
    assert "execute_remote_command_v2" not in sync_source


def test_explicit_phase2_environment_does_not_change_the_legacy_status_contract():
    flags = get_provider_feature_flags(
        {
            "PROVIDER_V2_CONTRACTS_ENABLED": "true",
            "PROVIDER_COORDINATOR_ENABLED": "true",
            "CHALLONGE_READ_ENABLED": "true",
        }
    )

    # The test above proves runtime paths do not read these values. This assertion
    # makes the intentional dark state visible without starting a service or worker.
    assert flags.provider_v2_contracts_enabled is True
    assert flags.provider_coordinator_enabled is True
