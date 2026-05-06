from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

SYSTEM_PROMPT = """
You are QueryCraft, a local AI assistant project built by Usaid.
You are part of a system that uses React, FastAPI, Ollama, and SQLite.

Important rules:
- QueryCraft is a local chatbot and data assistant project being built step by step.
- Do not invent company details, user groups, locations, regions, or product history.
- Do not assume facts that were not provided.
- If asked what QueryCraft is, say it is a local AI assistant/chatbot project for learning and building data-aware workflows.
- Keep answers clear, practical, and concise.
"""

def get_project_context():
    conn = sqlite3.connect("querycraft.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, description FROM projects")
    rows = cursor.fetchall()
    conn.close()

    context_lines = []
    for name, description in rows:
        context_lines.append(f"- {name}: {description}")

    return "\n".join(context_lines)

@app.get("/")
def root():
    return {"status": "backend running"}

@app.get("/projects")
def get_projects():
    conn = sqlite3.connect("querycraft.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description FROM projects")
    rows = cursor.fetchall()
    conn.close()

    return {
        "projects": [
            {"id": row[0], "name": row[1], "description": row[2]}
            for row in rows
        ]
    }

@app.post("/chat")
def chat(req: ChatRequest):
    db_context = get_project_context()

    full_prompt = f"""
{SYSTEM_PROMPT}

Here is known project data from the SQLite database:
{db_context}

User: {req.message}
Assistant:
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": full_prompt,
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()
    data = response.json()

    return {"reply": data.get("response", "")}


