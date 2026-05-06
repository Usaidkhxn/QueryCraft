import json
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import UPLOAD_DIR
from app.schemas import ChatRequest, ChatResponse, FolderIngestRequest
from app.services.metadata_service import get_schema_context
from app.services.chat_service import handle_chat, handle_chat_with_steps
from app.services.ingestion_service import (
    ingest_excel_file,
    ingest_zip_file,
    ingest_folder,
    get_ingestion_summary,
)

app = FastAPI(title="QueryCraft API")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "backend running"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return handle_chat(req.message)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    def event_generator():
        for event in handle_chat_with_steps(req.message):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@app.get("/schema")
def schema():
    return {"schema": get_schema_context()}


@app.post("/upload/excel")
async def upload_excel(file: UploadFile = File(...)):
    save_path = UPLOAD_DIR / file.filename

    with open(save_path, "wb") as f:
        f.write(await file.read())

    result = ingest_excel_file(str(save_path))

    return {
        "message": "Excel file ingested successfully.",
        "file": file.filename,
        "details": result,
    }


@app.post("/upload/zip")
async def upload_zip(file: UploadFile = File(...)):
    save_path = UPLOAD_DIR / file.filename

    with open(save_path, "wb") as f:
        f.write(await file.read())

    result = ingest_zip_file(str(save_path))

    return {
        "message": "ZIP file ingested successfully.",
        "file": file.filename,
        "details": result,
    }


@app.post("/ingest/folder")
def ingest_local_folder(req: FolderIngestRequest):
    result = ingest_folder(req.folder_path)

    return {
        "message": "Folder ingested successfully.",
        "details": result,
    }


@app.get("/ingestion/summary")
def ingestion_summary():
    return get_ingestion_summary()