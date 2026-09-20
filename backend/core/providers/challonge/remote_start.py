"""Guarded Challonge bracket-start capability."""
from __future__ import annotations

from dataclasses import dataclass


class RemoteStartUnavailable(RuntimeError):
    code = "remote_start_unsupported"


@dataclass(frozen=True)
class RemoteStartPreflight:
    provider: str = "challonge"
    allowed: bool = False
    reason_code: str = "remote_start_contract_unverified"
    message: str = "Challonge bracket start is unavailable until a documented mutation is supported."


class ChallongeRemoteStart:
    async def preflight(self, **_: object) -> RemoteStartPreflight:
        return RemoteStartPreflight()

    async def start(self, **_: object) -> dict[str, object]:
        raise RemoteStartUnavailable(RemoteStartPreflight().message)


__all__ = ["RemoteStartPreflight", "RemoteStartUnavailable", "ChallongeRemoteStart"]
