import sqlite3

def create_database():
    conn = sqlite3.connect("../var/primary/fuse/users.db")  
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            UserId INTEGER PRIMARY KEY,
            Username TEXT UNIQUE,
            Password TEXT,
            FullName Text,
            Roles TEXT
        )
    ''')

    conn.commit()
    conn.close()

create_database()
