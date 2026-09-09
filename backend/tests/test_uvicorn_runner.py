from __future__ import annotations

import asyncio

from backend.api.uvicorn_runner import selector_loop_factory


def test_uvicorn_runner_uses_selector_loop_factory():
    loop = selector_loop_factory(use_subprocess=False)
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()
