"""Seed the isolated acceptance database with an encrypted test Discord account.

The production token is decrypted in memory only and re-encrypted with the separate
acceptance key. Neither token nor destination is printed.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from seed_acceptance_challonge_account import load_env


async def main(source: str, target: str, source_key: str, target_key: str, application_id: str, channel_id: str) -> None:
    from backend.core import database
    from backend.core.integrations import (
        add_integration_destination, create_integration_account, get_integration_secret,
        list_integration_accounts, set_integration_secret,
    )
    os.environ["DATABASE_URL"] = source
    database.DATABASE_DSN = source
    os.environ["AITOB_INTEGRATION_MASTER_KEY"] = source_key
    source_accounts = [a for a in await list_integration_accounts() if a["provider_type"] == "discord" and a["status"] == "active"]
    if len(source_accounts) != 1:
        raise RuntimeError("Expected exactly one active local Discord account.")
    token = await get_integration_secret(source_accounts[0]["id"], "bot_token")
    if not token:
        raise RuntimeError("Local Discord account has no encrypted token.")
    os.environ["DATABASE_URL"] = target
    database.DATABASE_DSN = target
    os.environ["AITOB_INTEGRATION_MASTER_KEY"] = target_key
    await database.init_db()
    try:
        account = await create_integration_account("acceptance", "discord", application_id, "Acceptance Discord", metadata={"application_id": application_id})
    except Exception:
        accounts = [a for a in await list_integration_accounts("acceptance") if a["provider_type"] == "discord" and a["external_account_id"] == application_id]
        if len(accounts) != 1:
            raise
        account = accounts[0]
    await set_integration_secret(account["id"], "bot_token", token)
    try:
        await add_integration_destination(account["id"], "match_call_channel", channel_id, "Acceptance match calls")
    except Exception:
        pass
    print("acceptance_discord_account_seeded=ok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="source PostgreSQL DSN")
    parser.add_argument("--target", required=True, help="acceptance PostgreSQL DSN")
    parser.add_argument("--source-env", default=".env")
    parser.add_argument("--target-env", default=".env.acceptance")
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--channel-id", required=True)
    args = parser.parse_args()
    source_env = load_env(Path(args.source_env))
    target_env = load_env(Path(args.target_env))
    asyncio.run(main(args.source, args.target, source_env.get("AITOB_INTEGRATION_MASTER_KEY", ""), target_env.get("AITOB_INTEGRATION_MASTER_KEY", ""), args.application_id, args.channel_id))
