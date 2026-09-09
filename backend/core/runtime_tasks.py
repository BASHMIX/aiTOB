"""Own and drain service background tasks; no task starts at import time."""
import asyncio
import logging


class RuntimeTasks:
    def __init__(self):
        self.tasks = set()
        self.closed = False

    def start(self, coroutine):
        if self.closed:
            coroutine.close()
            raise RuntimeError("Service tasks are shutting down")
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self._finished)
        return task

    def _finished(self, task):
        self.tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logging.getLogger("aitob.runtime").error("Background task failed; error details withheld")

    async def close(self):
        self.closed = True
        pending = tuple(self.tasks)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self.tasks.clear()
