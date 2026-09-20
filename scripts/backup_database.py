"""Create a consistent PostgreSQL backup for recovery drills."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_path_for(backup: Path) -> Path:
    """Return the sidecar manifest path used by the backup tool."""
    return backup.with_suffix(backup.suffix + ".manifest.json")


def verify_manifest(backup: Path, manifest: Path | None = None) -> dict[str, object]:
    """Verify a backup against its redacted sidecar manifest.

    Restores must verify the exact artifact that was reviewed.  This check is
    deliberately local and does not open a database or contact a provider.
    """
    backup = backup.resolve()
    manifest = (manifest or manifest_path_for(backup)).resolve()
    if not backup.is_file():
        raise ValueError("backup does not exist")
    if not manifest.is_file():
        raise ValueError("backup manifest does not exist")
    try:
        record = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("backup manifest is unreadable") from exc
    if not isinstance(record, dict):
        raise ValueError("backup manifest is invalid")
    if record.get("file") != backup.name:
        raise ValueError("backup manifest does not identify this file")
    expected = record.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("backup manifest has no valid digest")
    actual = _digest(backup)
    if actual != expected:
        raise ValueError("backup digest does not match its manifest")
    expected_size = record.get("size_bytes")
    if expected_size is not None and expected_size != backup.stat().st_size:
        raise ValueError("backup size does not match its manifest")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".backups")
    args = parser.parse_args()

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

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
        "manifest_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "engine": engine,
        "file": target.name,
        "size_bytes": target.stat().st_size,
        "sha256": _digest(target),
        "secrets_included": False,
    }
    manifest_path = manifest_path_for(target)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"backup": str(target), "manifest": str(manifest_path), "engine": engine}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
