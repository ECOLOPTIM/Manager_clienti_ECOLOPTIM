import sqlite3

def create_atasamente_table():
    conn = sqlite3.connect("ecoloptim.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS atasamente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            nume TEXT NOT NULL,
            extensie TEXT NOT NULL,
            data TEXT NOT NULL,
            user TEXT,
            content BLOB
        )
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_atasamente_table()
    print("Table 'atasamente' created!")