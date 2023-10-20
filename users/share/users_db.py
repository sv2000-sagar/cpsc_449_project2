import sqlite3

def create_database():
    conn = sqlite3.connect("/home/r0bot/Desktop/cpsc_449_project2/users/var/users.db")  
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            UserId INTEGER PRIMARY KEY,
            Username TEXT UNIQUE,
            FirstName TEXT,
            LastName TEXT,
            Password TEXT,
            roles TEXT
        )
    ''')
    conn.execute("insert into Users(FirstName,LastName,Username,Password,roles) values('Jane','Doe2','Jane123', 'pass1','student');")
    conn.execute("insert into Users(FirstName,LastName,Username,Password,roles) values('John','Doe2','John123', 'pass2','instructor');")
    conn.execute("insert into Users(FirstName,LastName,Username,Password,roles) values('Jake','Doe3','Jake123', 'pass3','registrar');")
    

    conn.commit()
    conn.close()

create_database()
