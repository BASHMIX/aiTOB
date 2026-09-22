"""Phase 11 guard: canonical Start.gg paths have no migration switch."""
from pathlib import Path

from backend.core.provider_feature_flags import get_provider_feature_flags


def test_startgg_reads_use_the_coordinator_without_a_migration_branch():
    root = Path(__file__).resolve().parents[1]
    source = (root / "core" / "provider_sync_manager.py").read_text(encoding="utf-8")

    assert "SyncCoordinator" in source
    assert "provider.fetch_snapshot(request)" in source


def test_only_real_challonge_rollout_flags_remain():
    flags = get_provider_feature_flags({"CHALLONGE_READ_ENABLED": "true"})

    assert flags.challonge_read_enabled is True
    assert set(flags.__dataclass_fields__) == {
        "challonge_read_enabled",
        "challonge_local_workflow_enabled",
        "challonge_score_commands_enabled",
        "challonge_dq_commands_enabled",
        "tournament_setup_wizard_enabled",
        "tournament_activation_enabled",
        "tournament_registration_enabled",
        "provider_start_enabled",
    }
