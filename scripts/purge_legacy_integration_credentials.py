"""Irreversibly remove verified legacy integration credentials.

Run only after `migrate_integration_accounts.py` reports success and both provider
and Discord acceptance checks are recorded.  The caller must create a backup first.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path


LEGACY_KEYS = {
    "DISCORD_BOT_TOKEN", "MATCH_CALL_CHANNEL_ID", "CHALLONGE_API_KEY",
    "CHALLONGE_OAUTH_CLIENT_ID", "CHALLONGE_OAUTH_CLIENT_SECRET",
    "CHALLONGE_OAUTH_REDIRECT_URI", "CHALLONGE_OAUTH_ACCESS_TOKEN",
    "CHALLONGE_OAUTH_REFRESH_TOKEN", "CHALLONGE_OAUTH_EXPIRES_AT",
}


async def purge(db_path: str) -> int:
    from backend.core import database
    from backend.core.integrations import get_integration_secret, list_integration_accounts
    database.DB_PATH = db_path
    accounts = await list_integration_accounts()
    for account in accounts:
        if account["provider_type"] == "discord" and not await get_integration_secret(account["id"], "bot_token"):
            raise RuntimeError("Discord encrypted credential verification is missing.")
        if account["provider_type"] == "challonge" and not (await get_integration_secret(account["id"], "access_token") or await get_integration_secret(account["id"], "api_key")):
            raise RuntimeError("Challonge encrypted credential verification is missing.")
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        placeholders = ",".join("?" for _ in LEGACY_KEYS)
        a = await db.execute(f"DELETE FROM global_settings WHERE key IN ({placeholders})", tuple(LEGACY_KEYS))
        b = await db.execute(f"DELETE FROM connections WHERE key IN ({placeholders})", tuple(LEGACY_KEYS))
        await db.commit()
    return a.rowcount + b.rowcount


def scrub_env(path: Path) -> None:
    if not path.exists():
        return
    kept = [line for line in path.read_text(encoding="utf-8").splitlines() if line.split("=", 1)[0].strip() not in LEGACY_KEYS]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Pass --apply only after verified acceptance evidence and a backup.")
    removed = asyncio.run(purge(args.database))
    scrub_env(Path(args.env_file))
    print(f"legacy_credentials_removed={removed}")
