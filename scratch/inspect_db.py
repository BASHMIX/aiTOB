import sqlite3
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def inspect():
    db_path = os.path.join(PROJECT_ROOT, "backend", "core", "database.sqlite")
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        print("Start the API at least once (`python run.py`) so init_db() creates the schema.")
        return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== GLOBAL SETTINGS ===")
    try:
        cursor.execute("SELECT key, value FROM global_settings")
        for row in cursor.fetchall():
            print(f"{row['key']}: {row['value']}")
    except Exception as e:
        print("Error reading global_settings:", e)
        
    print("\n=== CONNECTIONS ===")
    try:
        cursor.execute("SELECT key, value FROM connections")
        for row in cursor.fetchall():
            print(f"{row['key']}: {row['value']}")
    except Exception as e:
        print("Error reading connections:", e)
        
    conn.close()

if __name__ == "__main__":
    inspect()
