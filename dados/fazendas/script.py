import sqlite3

conn = sqlite3.connect("1.db")
cursor = conn.cursor()

cursor.execute("PRAGMA foreign_key_list(logs)")
relacionamentos = cursor.fetchall()

print(relacionamentos)
