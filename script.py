import sqlite3
c = sqlite3.connect("banco.db")
for nome, sql in c.execute("SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"):
    print(sql + ";\n")