"""Product rollout flags for Challonge and Tournament Setup.

Every flag is disabled unless its environment variable is explicitly set to a
truthy value.  Keeping the rollout controls in one immutable projection gives
API, bot, and worker code the same fail-closed defaults while allowing the
wizard, activation, registration, and remote provider-start gates to be
enabled independently during cutover.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ProviderFeatureFlags:
    # Provider product rollout gates.
    challonge_read_enabled: bool = False
    challonge_local_workflow_enabled: bool = False
    challonge_score_commands_enabled: bool = False
    challonge_dq_commands_enabled: bool = False

    # Tournament Setup rollout gates.  These must remain dark until the
    # prerequisite and acceptance evidence described in specs/004 is complete.
    tournament_setup_wizard_enabled: bool = False
    tournament_activation_enabled: bool = False
    tournament_registration_enabled: bool = False
    provider_start_enabled: bool = False


def _flag(environment: Mapping[str, str], *names: str) -> bool:
    """Read a flag using the first configured name, preserving false values.

    The unprefixed names are canonical and match ``.env.example``.  The
    ``AITOB_`` aliases make the rollout safe for deployments that namespace all
    application settings while keeping one projection for callers.
    """
    for name in names:
        if name in environment:
            return _enabled(environment.get(name))
    return False


def get_provider_feature_flags(
    environment: Mapping[str, str] | None = None,
) -> ProviderFeatureFlags:
    """Read flags without caching so tests and controlled rollout stay explicit."""
    env = environment if environment is not None else os.environ
    return ProviderFeatureFlags(
        challonge_read_enabled=_enabled(env.get("CHALLONGE_READ_ENABLED")),
        challonge_local_workflow_enabled=_enabled(
            env.get("CHALLONGE_LOCAL_WORKFLOW_ENABLED")
        ),
        challonge_score_commands_enabled=_enabled(
            env.get("CHALLONGE_SCORE_COMMANDS_ENABLED")
        ),
        challonge_dq_commands_enabled=_enabled(env.get("CHALLONGE_DQ_COMMANDS_ENABLED")),
        tournament_setup_wizard_enabled=_flag(
            env,
            "TOURNAMENT_SETUP_WIZARD_ENABLED",
            "AITOB_TOURNAMENT_SETUP_WIZARD_ENABLED",
        ),
        tournament_activation_enabled=_flag(
            env,
            "TOURNAMENT_ACTIVATION_ENABLED",
            "AITOB_TOURNAMENT_ACTIVATION_ENABLED",
        ),
        tournament_registration_enabled=_flag(
            env,
            "TOURNAMENT_REGISTRATION_ENABLED",
            "AITOB_TOURNAMENT_REGISTRATION_ENABLED",
        ),
        provider_start_enabled=_flag(
            env,
            "PROVIDER_START_ENABLED",
            "AITOB_PROVIDER_START_ENABLED",
        ),
    )
