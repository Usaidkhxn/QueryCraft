from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DB_PATH = str(BASE_DIR / "querycraft.db")
UPLOAD_DIR = BASE_DIR / "uploads"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

ALLOWED_SQL_TABLES = {
    "projects",
    "metrics_long",
    "data_dictionary",
    "ingested_files",
}