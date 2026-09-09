"""Windows-safe uvicorn entrypoint for the PostgreSQL async transport.

psycopg's async connection requires the Selector event loop on Windows.  The
normal ``uvicorn`` console script creates its event loop before importing the
application, which is too late for ``storage.py`` to change the policy.  Keep
the policy setup in this tiny process entrypoint so API startup and shutdown
use the same loop in development and containers.
"""
from __future__ import annotations

import asyncio
import sys
import argparse


def selector_loop_factory(*, use_subprocess: bool = False):
    """Force a Selector loop; uvicorn otherwise chooses Proactor on Windows."""
    return asyncio.SelectorEventLoop()


def main() -> None:
    if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    import uvicorn

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args, _ = parser.parse_known_args()
    uvicorn.run(
        "backend.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        loop="backend.api.uvicorn_runner:selector_loop_factory",
    )


if __name__ == "__main__":
    main()
