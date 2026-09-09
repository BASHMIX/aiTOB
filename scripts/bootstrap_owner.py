"""One-time, local-only initial Owner bootstrap.

Reads credentials interactively so neither value is put in command history, a
configuration file, or process arguments.  It is intentionally suitable only
while the application is using the explicit SQLite migration-tool mode.
"""

from __future__ import annotations

import asyncio
import getpass
import os


async def main() -> None:
    os.environ.setdefault("AITOB_SQLITE_MIGRATION_TOOL", "1")
    email = input("Owner email: ").strip()
    password = getpass.getpass("Owner password: ")
    display_name = input("Owner display name [Owner]: ").strip() or "Owner"
    workspace_name = input(f"Workspace name [{display_name} workspace]: ").strip() or f"{display_name} workspace"
    os.environ["AITOB_BOOTSTRAP_OWNER_EMAIL"] = email
    os.environ["AITOB_BOOTSTRAP_OWNER_PASSWORD"] = password
    os.environ["AITOB_BOOTSTRAP_OWNER_NAME"] = display_name
    os.environ["AITOB_BOOTSTRAP_WORKSPACE_NAME"] = workspace_name

    from backend.core.database import init_db

    await init_db()
    print("Initial owner bootstrap completed.")


if __name__ == "__main__":
    asyncio.run(main())
