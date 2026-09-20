"""Guarded Start.gg bracket-start capability.

Start.gg does not expose a documented public mutation for starting a bracket
through the integration.  The wizard therefore reports an explicit blocked
preflight and never attempts browser automation or an undocumented mutation.
"""
from __future__ import annotations

from dataclasses import dataclass


class RemoteStartUnavailable(RuntimeError):
    code = "remote_start_unsupported"


@dataclass(frozen=True)
class RemoteStartPreflight:
    provider: str = "startgg"
    allowed: bool = False
    reason_code: str = "remote_start_contract_unverified"
    message: str = "Start.gg bracket start is unavailable until a documented mutation is supported."


class StartGGRemoteStart:
    async def preflight(self, **_: object) -> RemoteStartPreflight:
        return RemoteStartPreflight()

    async def start(self, **_: object) -> dict[str, object]:
        raise RemoteStartUnavailable(RemoteStartPreflight().message)


__all__ = ["RemoteStartPreflight", "RemoteStartUnavailable", "StartGGRemoteStart"]
