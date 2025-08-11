import sqlite3

def init_db():
    conn = sqlite3.connect('ebites.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INT PRIMARY KEY, name TEXT, age INT, gender TEXT, city TEXT)''')
    conn.commit()
    conn.close()