from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    content_type: str | None = None
    status: str = "registered"
    next_step: str = "POST /ingest/{document_id}"


class DocumentIngestResponse(BaseModel):
    document_id: str
    status: str
    chunks_indexed: int = 0
    warnings: list[str] = Field(default_factory=list)
