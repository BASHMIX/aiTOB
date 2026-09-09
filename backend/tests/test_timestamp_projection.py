from datetime import UTC, datetime

from backend.core.organizer_console import _alive
from backend.core.timestamps import as_utc


def test_naive_postgres_and_sqlite_utc_timestamp_have_same_meaning():
    stamp = datetime(2026, 9, 8, 12, 30)
    assert as_utc(stamp) == as_utc("2026-09-08T12:30:00Z")
    assert as_utc(stamp).tzinfo == UTC


def test_console_accepts_postgres_timestamp_objects():
    assert _alive(datetime.now(UTC).replace(tzinfo=None))
