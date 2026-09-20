"""Copy one locally stored Challonge account into the isolated acceptance DB.

This transfers decrypted bytes only in memory and immediately re-encrypts them with
the acceptance service key. It never prints account IDs or credential values.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value
    return values


async def main(source: str, target: str, source_key: str, target_key: str) -> None:
    from backend.core import database
    from backend.core.integrations import (
        create_integration_account, get_integration_secret, list_integration_accounts,
        set_integration_secret,
    )
    os.environ["DATABASE_URL"] = source
    database.DATABASE_DSN = source
    os.environ["AITOB_INTEGRATION_MASTER_KEY"] = source_key
    source_accounts = [a for a in await list_integration_accounts() if a["provider_type"] == "challonge" and a["status"] == "active"]
    if len(source_accounts) != 1:
        raise RuntimeError("Expected exactly one active local Challonge account.")
    source_account = source_accounts[0]
    credentials = {kind: await get_integration_secret(source_account["id"], kind) for kind in ("api_key", "access_token", "refresh_token")}
    os.environ["DATABASE_URL"] = target
    database.DATABASE_DSN = target
    os.environ["AITOB_INTEGRATION_MASTER_KEY"] = target_key
    await database.init_db()
    try:
        target_account = await create_integration_account("acceptance", "challonge", "acceptance-source", "Acceptance Challonge", metadata={})
    except Exception:
        accounts = [a for a in await list_integration_accounts("acceptance") if a["provider_type"] == "challonge"]
        if len(accounts) != 1:
            raise
        target_account = accounts[0]
    for kind, value in credentials.items():
        if value:
            await set_integration_secret(target_account["id"], kind, value)
    print("acceptance_challonge_account_seeded=ok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="source PostgreSQL DSN")
    parser.add_argument("--target", required=True, help="acceptance PostgreSQL DSN")
    parser.add_argument("--source-env", default=".env")
    parser.add_argument("--target-env", default=".env.acceptance")
    args = parser.parse_args()
    source_env = load_env(Path(args.source_env))
    target_env = load_env(Path(args.target_env))
    asyncio.run(main(args.source, args.target, source_env.get("AITOB_INTEGRATION_MASTER_KEY", ""), target_env.get("AITOB_INTEGRATION_MASTER_KEY", "")))
