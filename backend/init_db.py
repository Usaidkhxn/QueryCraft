import sqlite3

conn = sqlite3.connect("querycraft.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM projects")

sample_data = [
    ("QueryCraft", "A local AI assistant/chatbot project built with React, FastAPI, Ollama, and SQLite."),
    ("IPEDS App", "A university clustering and comparison app using institutional data."),
    ("Pavement Sync", "A synchronized pavement viewing app using Python, PySide6, and OpenCV.")
]

cursor.executemany(
    "INSERT INTO projects (name, description) VALUES (?, ?)",
    sample_data
)

conn.commit()
conn.close()

print("Database created and sample data inserted.")