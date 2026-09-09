"""Migration must never silently discard a source field, even on an empty table."""
import sqlite3

import pytest

from scripts import migrate_sqlite_to_postgres as migration


def test_unmapped_source_column_blocks_copy_before_target_write(monkeypatch):
    with sqlite3.connect(":memory:") as source:
        source.execute("CREATE TABLE sample (id TEXT, legacy_metadata TEXT)")
        monkeypatch.setattr(migration, "target_columns", lambda target, table: ["id"])
        with pytest.raises(RuntimeError, match="Unmapped source columns"):
            migration.copy_table(source, object(), "sample")
