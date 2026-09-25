"""Fail-closed rollout dependencies for staged tournament features."""
from __future__ import annotations

from fastapi import HTTPException

from backend.core.provider_feature_flags import get_provider_feature_flags


def _require(enabled: bool, code: str, message: str) -> None:
    if not enabled:
        raise HTTPException(
            status_code=409,
            detail={"code": code, "message": message, "retryable": False},
        )


def require_tournament_setup_wizard_enabled() -> None:
    _require(
        get_provider_feature_flags().tournament_setup_wizard_enabled,
        "tournament_setup_wizard_disabled",
        "Tournament setup is disabled by the current rollout setting.",
    )


def require_tournament_activation_enabled() -> None:
    _require(
        get_provider_feature_flags().tournament_activation_enabled,
        "tournament_activation_disabled",
        "Tournament materialization and activation are disabled by the current rollout setting.",
    )


def require_tournament_registration_enabled() -> None:
    _require(
        get_provider_feature_flags().tournament_registration_enabled,
        "tournament_registration_disabled",
        "Tournament registration is disabled by the current rollout setting.",
    )


def require_provider_start_enabled() -> None:
    _require(
        get_provider_feature_flags().provider_start_enabled,
        "provider_start_disabled",
        "Remote provider lifecycle actions are disabled by the current rollout setting.",
    )


__all__ = [
    "require_tournament_setup_wizard_enabled",
    "require_tournament_activation_enabled",
    "require_tournament_registration_enabled",
    "require_provider_start_enabled",
]
