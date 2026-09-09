"""Backup, dry-run, and apply the encrypted account migration without secret output."""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
    with sqlite3.connect(f"file:{destination.as_posix()}?mode=ro", uri=True) as verified:
        verified.execute("PRAGMA integrity_check").fetchone()


async def migrate(database_path: Path) -> dict:
    from backend.core import database
    from backend.core.integrations import get_integration_secret, migrate_legacy_integrations

    database.DB_PATH = str(database_path)
    await database.init_db()
    from backend.core.workspace_auth import legacy_owner_principal
    owner = await legacy_owner_principal()
    if not owner:
        raise RuntimeError("An active Owner workspace must exist before integration migration.")
    report = await migrate_legacy_integrations(owner.workspace_id)
    for account_key, secret_type in (("discord_account_id", "bot_token"), ("challonge_account_id", "access_token")):
        account_id = report.get(account_key)
        if account_id and await get_integration_secret(account_id, secret_type) is None:
            raise RuntimeError("Encrypted credential verification failed.")
    return {"migrated_accounts": report["migrated_accounts"], "verified": True, "legacy_retained": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--backup-dir", default=".migration-backups")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = Path(args.database).resolve()
    if not source.exists():
        raise SystemExit("Database was not found.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = Path(args.backup_dir) / f"{source.stem}-{stamp}.sqlite"
    backup(source, backup_path)
    target = source if args.apply else backup_path
    old = os.environ.get("DB_PATH")
    try:
        result = asyncio.run(migrate(target))
    finally:
        if old is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = old
    print(f"migration={'applied' if args.apply else 'dry-run'} verified={result['verified']} legacy_retained={result['legacy_retained']} accounts={result['migrated_accounts']}")


if __name__ == "__main__":
    main()
