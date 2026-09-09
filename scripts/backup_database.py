"""Create a consistent, redacted database backup for recovery drills.

PostgreSQL is the runtime source of truth. SQLite is accepted only when the
caller explicitly passes ``--sqlite`` for a migration/recovery fixture.
Secrets are never printed; the output path and row-level manifest are safe
metadata only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".backups")
    parser.add_argument("--sqlite", action="store_true", help="explicitly back up a SQLite migration fixture")
    parser.add_argument("--source", help="SQLite source path when --sqlite is used")
    args = parser.parse_args()

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.sqlite:
        source = Path(args.source or os.getenv("DB_PATH", "")).resolve()
        if not source.exists():
            raise SystemExit("SQLite source does not exist")
        target = out_dir / f"aitob-{stamp}.sqlite"
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        engine = "sqlite-fixture"
    else:
        dsn = os.getenv("DATABASE_URL", "").strip()
        if not dsn or not dsn.startswith(("postgresql://", "postgres://")):
            raise SystemExit("DATABASE_URL must be a PostgreSQL DSN for runtime backups")
        target = out_dir / f"aitob-{stamp}.dump"
        result = subprocess.run(["pg_dump", "--format=custom", "--file", str(target), dsn], check=False)
        if result.returncode:
            target.unlink(missing_ok=True)
            raise SystemExit("pg_dump failed")
        engine = "postgresql"

    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "engine": engine,
        "file": target.name,
        "sha256": _digest(target),
        "secrets_included": False,
    }
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"backup": str(target), "manifest": str(manifest_path), "engine": engine}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
