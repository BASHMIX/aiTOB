from backend.core.provider_feature_flags import get_provider_feature_flags


def test_provider_migration_flags_are_dark_by_default():
    flags = get_provider_feature_flags({})

    assert flags.provider_v2_contracts_enabled is False
    assert flags.provider_coordinator_enabled is False
    assert flags.challonge_read_enabled is False
    assert flags.challonge_local_workflow_enabled is False
    assert flags.challonge_score_commands_enabled is False
    assert flags.challonge_dq_commands_enabled is False


def test_provider_migration_flags_require_explicit_truthy_values():
    flags = get_provider_feature_flags(
        {
            "PROVIDER_V2_CONTRACTS_ENABLED": "true",
            "PROVIDER_COORDINATOR_ENABLED": "1",
            "CHALLONGE_READ_ENABLED": "yes",
            "CHALLONGE_LOCAL_WORKFLOW_ENABLED": "on",
            "CHALLONGE_SCORE_COMMANDS_ENABLED": "false",
            "CHALLONGE_DQ_COMMANDS_ENABLED": "0",
        }
    )

    assert flags.provider_v2_contracts_enabled is True
    assert flags.provider_coordinator_enabled is True
    assert flags.challonge_read_enabled is True
    assert flags.challonge_local_workflow_enabled is True
    assert flags.challonge_score_commands_enabled is False
    assert flags.challonge_dq_commands_enabled is False
