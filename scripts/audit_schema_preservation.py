"""Read-only source-schema inventory; prints column names, never data values."""
import argparse
from pathlib import Path
import sqlite3
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.core.database_schema import TABLE_SCHEMAS, MIGRATIONS


def audit(source_path):
    source = sqlite3.connect(Path(source_path).resolve().as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(":memory:")
    try:
        for statement in TABLE_SCHEMAS:
            target.execute(statement)
        for statement in MIGRATIONS:
            try:
                target.execute(statement)
            except sqlite3.OperationalError as exc:
                if not str(exc).startswith("duplicate column name"):
                    raise
        missing = {}
        for (table,) in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            quoted = '"' + table.replace('"', '""') + '"'
            old = {row[1] for row in source.execute(f"PRAGMA table_info({quoted})")}
            new = {row[1] for row in target.execute(f"PRAGMA table_info({quoted})")}
            if old - new:
                missing[table] = sorted(old - new)
        return missing
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    report = audit(args.source)
    print(json.dumps({"unmapped_columns": report}))
    sys.exit(1 if report else 0)
