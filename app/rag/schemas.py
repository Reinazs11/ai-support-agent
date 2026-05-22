from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceCitation(BaseModel):
    document_id: str
    title: str
    chunk_id: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    confidence: str = "unknown"
    retrieval_status: str = "not_configured"
