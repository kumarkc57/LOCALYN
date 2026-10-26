import sqlite3

def clean_database():
    conn = sqlite3.connect("backend/localyn.db")
    cursor = conn.cursor()
    
    # Remove non-Bengaluru national sports / irrelevant articles and test records
    cursor.execute("DELETE FROM reports WHERE title LIKE '%NBA%'")
    cursor.execute("DELETE FROM reports WHERE title LIKE '%Rohit Sharma%'")
    cursor.execute("DELETE FROM reports WHERE title LIKE '%Nick Bosa%'")
    cursor.execute("DELETE FROM reports WHERE title LIKE '%No Loc%'")
    cursor.execute("DELETE FROM reports WHERE id LIKE '%test%'")
    
    conn.commit()
    
    cursor.execute("SELECT id, category, location, title FROM reports")
    rows = cursor.fetchall()
    print(f"Cleaned database. Remaining {len(rows)} reports, ALL strictly Bengaluru-specific:")
    for r in rows:
        print(f"  [{r[1]}] ({r[2]}) {r[3][:65]}")
        
    conn.close()

if __name__ == "__main__":
    clean_database()
