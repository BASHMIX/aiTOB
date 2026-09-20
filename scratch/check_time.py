import sqlite3
import datetime

conn = sqlite3.connect('backend/core/database.sqlite')
cursor = conn.cursor()
cursor.execute("SELECT value FROM global_settings WHERE key='bot_last_seen'")
row = cursor.fetchone()
print("DB last seen:", row)
print("Current time:", datetime.datetime.now().isoformat())
conn.close()
