import sqlite3, os

db = "backend/core/database.sqlite"
print("DB exists:", os.path.exists(db))
if os.path.exists(db):
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in c.fetchall()]
    print("Tables:", tables)
    print("global_settings present:", "global_settings" in tables)
    conn.close()
else:
    print("No database file found - init_db() has never been run.")
