"""Unit test for start_test.py's --purge clean-slate residue wipe.

Builds a tiny SQLite with the residue tables, seeds rows, runs _purge_residue,
and asserts everything that accumulates across a test run is cleared.
"""
import sqlite3
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_start_test():
    path = os.path.join(ROOT, "start_test.py")
    spec = importlib.util.spec_from_file_location("start_test_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_purge_residue_clears_everything():
    st = _load_start_test()
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE bot_feed (id INTEGER PRIMARY KEY, message TEXT);
        CREATE TABLE hub_commands (id INTEGER PRIMARY KEY, command TEXT);
        CREATE TABLE conflicts (id INTEGER PRIMARY KEY, set_id TEXT);
        CREATE TABLE planned_streams (set_id TEXT PRIMARY KEY, tournament_slug TEXT);
        CREATE TABLE global_settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE active_matches (set_id TEXT PRIMARY KEY, is_stream_match INTEGER, station_id TEXT);
        INSERT INTO bot_feed (message) VALUES ('old log');
        INSERT INTO hub_commands (command) VALUES ('call_match x');
        INSERT INTO conflicts (set_id) VALUES ('s1');
        INSERT INTO planned_streams (set_id, tournament_slug) VALUES ('s1', 't');
        INSERT INTO global_settings (key, value) VALUES ('_dispatcher_stop_signaled_t_100', '1');
        INSERT INTO global_settings (key, value) VALUES ('auto_dispatch_master_switch', 'on');
        INSERT INTO active_matches (set_id, is_stream_match, station_id) VALUES ('s1', 1, 'station_1');
        """
    )
    conn.commit()

    st._purge_residue(cur)
    conn.commit()

    assert cur.execute("SELECT COUNT(*) FROM bot_feed").fetchone()[0] == 0
    assert cur.execute("SELECT COUNT(*) FROM hub_commands").fetchone()[0] == 0
    assert cur.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0] == 0
    assert cur.execute("SELECT COUNT(*) FROM planned_streams").fetchone()[0] == 0
    assert cur.execute(
        "SELECT COUNT(*) FROM global_settings WHERE key LIKE '_dispatcher_stop_signaled_%'"
    ).fetchone()[0] == 0
    assert cur.execute(
        "SELECT value FROM global_settings WHERE key='auto_dispatch_master_switch'"
    ).fetchone()[0] == "off"
    row = cur.execute("SELECT is_stream_match, station_id FROM active_matches WHERE set_id='s1'").fetchone()
    assert row == (0, None)
    conn.close()


def test_purge_residue_tolerates_missing_tables():
    # Older DB revisions may lack some tables — purge must skip them, not crash.
    st = _load_start_test()
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE bot_feed (id INTEGER PRIMARY KEY, message TEXT)")
    cur.execute("INSERT INTO bot_feed (message) VALUES ('x')")
    conn.commit()
    st._purge_residue(cur)  # must not raise despite the other tables being absent
    conn.commit()
    assert cur.execute("SELECT COUNT(*) FROM bot_feed").fetchone()[0] == 0
    conn.close()
