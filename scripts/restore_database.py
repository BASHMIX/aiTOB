"""Restore a backup to an explicitly named disposable target.

The command refuses to overwrite a non-empty target unless ``--force`` is
provided. Production cutover is intentionally a separate, reviewed runbook.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
from pathlib import Path

from backup_database import manifest_path_for, verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument("--sqlite-target", type=Path)
    parser.add_argument("--postgres-target", help="explicit PostgreSQL DSN")
    parser.add_argument(
        "--manifest",
        type=Path,
        help="sidecar manifest to verify (defaults to <backup>.manifest.json)",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    backup = args.backup.resolve()
    if not backup.exists():
        raise SystemExit("backup does not exist")
    try:
        manifest = verify_manifest(backup, args.manifest)
    except ValueError as exc:
        raise SystemExit(f"refusing restore: {exc}") from exc
    if backup.suffix == ".sqlite":
        if not args.sqlite_target:
            raise SystemExit("--sqlite-target is required for SQLite restore")
        target = args.sqlite_target.resolve()
        if target.exists() and target.stat().st_size and not args.force:
            raise SystemExit("refusing to overwrite a non-empty SQLite target; use --force explicitly")
        target.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(f"file:{backup}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        print(f"restored sqlite backup to {target} (manifest verified: {manifest['sha256'][:12]}…)")
        return 0
    dsn = args.postgres_target or os.getenv("DATABASE_URL", "").strip()
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise SystemExit("an explicit PostgreSQL target DSN is required")
    result = subprocess.run(["pg_restore", "--clean", "--if-exists", "--dbname", dsn, str(backup)], check=False)
    if result.returncode:
        raise SystemExit("pg_restore failed")
    print("restored PostgreSQL backup to the explicitly supplied target (manifest verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
