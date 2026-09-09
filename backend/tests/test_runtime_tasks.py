import asyncio
import pytest
from backend.core.runtime_tasks import RuntimeTasks


@pytest.mark.asyncio
async def test_service_shutdown_waits_for_cleanup_and_rejects_new_tasks():
    tasks = RuntimeTasks()
    started, cleaned = asyncio.Event(), asyncio.Event()
    async def work():
        started.set()
        try:
            await asyncio.Future()
        finally:
            await asyncio.sleep(0.01)
            cleaned.set()
    task = tasks.start(work())
    await started.wait()
    await tasks.close()
    assert cleaned.is_set() and task.done() and not tasks.tasks
    with pytest.raises(RuntimeError):
        tasks.start(work())
