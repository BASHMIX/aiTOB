"""Frozen adapter-level behavior before the provider V2 migration is enabled."""
from unittest.mock import AsyncMock

import pytest

from backend.core.contracts import ProviderSetState
from backend.core.providers.startgg.provider import StartGGProvider


@pytest.mark.asyncio
async def test_startgg_baseline_live_and_dq_commands_keep_native_client_calls():
    client = AsyncMock()
    client.mark_in_progress.return_value = True
    client.mark_set_dq.return_value = True
    provider = StartGGProvider(client=client)

    live = await provider.mark_in_progress("set-1")
    dq = await provider.mark_dq("set-1", "entrant-1")

    assert (live.success, live.new_state) == (True, ProviderSetState.IN_PROGRESS)
    assert (dq.success, dq.new_state) == (True, ProviderSetState.COMPLETE)
    client.mark_in_progress.assert_awaited_once_with("set-1")
    client.mark_set_dq.assert_awaited_once_with("set-1", "entrant-1")
    client.assign_stream.assert_not_called()


@pytest.mark.asyncio
async def test_startgg_baseline_reset_and_stream_queue_remain_separate_actions():
    client = AsyncMock()
    client.reset_set.return_value = True
    client.assign_stream.return_value = True
    client.remove_stream.return_value = True
    provider = StartGGProvider(client=client)

    reset = await provider.reset_set("set-2")
    assigned = await provider.assign_stream("set-2", "stream-1")
    removed = await provider.remove_stream("set-2")

    assert (reset.success, reset.new_state) == (True, ProviderSetState.NOT_STARTED)
    assert assigned.success is True
    assert removed.success is True
    client.reset_set.assert_awaited_once_with("set-2")
    client.assign_stream.assert_awaited_once_with("set-2", "stream-1")
    client.remove_stream.assert_awaited_once_with("set-2")
