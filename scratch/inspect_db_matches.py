import sqlite3
import os

def inspect():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(script_dir, "..", "backend", "core", "database.sqlite"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== TOURNAMENTS ===")
    try:
        cursor.execute("SELECT slug, name, game FROM tournaments")
        rows = cursor.fetchall()
        print(f"Total tournaments: {len(rows)}")
        for row in rows:
            print(f"Slug: {row['slug']}, Name: {row['name']}, Game: {row['game']}")
    except Exception as e:
        print("Error reading tournaments:", e)
        
    print("\n=== ACTIVE MATCHES ===")
    try:
        cursor.execute("SELECT set_id, tournament_slug, p1_name, p2_name, status FROM active_matches")
        rows = cursor.fetchall()
        print(f"Total active matches: {len(rows)}")
        for row in rows:
            print(f"Set: {row['set_id']}, Tournament: {row['tournament_slug']}, P1: {row['p1_name']}, P2: {row['p2_name']}, Status: {row['status']}")
    except Exception as e:
        print("Error reading active_matches:", e)
        
    conn.close()

if __name__ == "__main__":
    inspect()
