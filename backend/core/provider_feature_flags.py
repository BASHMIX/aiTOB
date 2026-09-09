"""Dark-launch flags for the provider-isolation migration.

All flags default to false.  Defining them here is intentionally inert: legacy
Start.gg consumers keep their current code paths until a later, explicitly gated
phase adopts the V2 contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ProviderFeatureFlags:
    provider_v2_contracts_enabled: bool = False
    provider_coordinator_enabled: bool = False
    challonge_read_enabled: bool = False
    challonge_local_workflow_enabled: bool = False
    challonge_score_commands_enabled: bool = False
    challonge_dq_commands_enabled: bool = False


def get_provider_feature_flags(
    environment: Mapping[str, str] | None = None,
) -> ProviderFeatureFlags:
    """Read flags without caching so tests and controlled rollout stay explicit."""
    env = environment if environment is not None else os.environ
    return ProviderFeatureFlags(
        provider_v2_contracts_enabled=_enabled(env.get("PROVIDER_V2_CONTRACTS_ENABLED")),
        provider_coordinator_enabled=_enabled(env.get("PROVIDER_COORDINATOR_ENABLED")),
        challonge_read_enabled=_enabled(env.get("CHALLONGE_READ_ENABLED")),
        challonge_local_workflow_enabled=_enabled(
            env.get("CHALLONGE_LOCAL_WORKFLOW_ENABLED")
        ),
        challonge_score_commands_enabled=_enabled(
            env.get("CHALLONGE_SCORE_COMMANDS_ENABLED")
        ),
        challonge_dq_commands_enabled=_enabled(env.get("CHALLONGE_DQ_COMMANDS_ENABLED")),
    )
