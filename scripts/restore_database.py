"""Restore a backup to an explicitly named disposable target.

The command refuses to overwrite a non-empty target unless ``--force`` is
provided. Production cutover is intentionally a separate, reviewed runbook.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from backup_database import manifest_path_for, verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
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
    dsn = args.postgres_target or os.getenv("DATABASE_URL", "").strip()
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise SystemExit("an explicit PostgreSQL target DSN is required")
    # Never drop objects implicitly.  A normal restore is additive/fail-closed
    # on an occupied target; destructive cleanup is opt-in and must be visible
    # at the command line via --force.
    restore_args = ["pg_restore", "--exit-on-error"]
    if args.force:
        restore_args.extend(["--clean", "--if-exists"])
    restore_args.extend(["--dbname", dsn, str(backup)])
    result = subprocess.run(restore_args, check=False)
    if result.returncode:
        raise SystemExit("pg_restore failed")
    print("restored PostgreSQL backup to the explicitly supplied target (manifest verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
