from pydantic import BaseModel
from typing import Any, List, Optional


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    mode: str
    reply: str
    sql: Optional[str] = None
    results: Optional[List[dict[str, Any]]] = None
    evidence: Optional[List[str]] = None
    error: Optional[str] = None


class FolderIngestRequest(BaseModel):
    folder_path: str