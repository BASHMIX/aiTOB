import pytest

from backend.core.providers.startgg.remote_start import StartGGRemoteStart
from backend.core.providers.challonge.remote_start import ChallongeRemoteStart


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter,provider", [(StartGGRemoteStart(), "startgg"), (ChallongeRemoteStart(), "challonge")])
async def test_remote_start_is_truthfully_blocked_without_documented_mutation(adapter, provider):
    preflight = await adapter.preflight()
    assert preflight.provider == provider
    assert preflight.allowed is False
    with pytest.raises(RuntimeError):
        await adapter.start()
