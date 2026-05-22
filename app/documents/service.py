from uuid import uuid4

from fastapi import UploadFile

from app.documents.schemas import DocumentIngestResponse, DocumentUploadResponse


class DocumentService:
    async def register_upload(self, file: UploadFile) -> DocumentUploadResponse:
        return DocumentUploadResponse(
            document_id=str(uuid4()),
            filename=file.filename or "uploaded-document",
            content_type=file.content_type,
        )

    async def ingest(self, document_id: str) -> DocumentIngestResponse:
        return DocumentIngestResponse(
            document_id=document_id,
            status="pending_integration",
            warnings=[
                "Persistence, parsing, embedding generation, and Qdrant indexing are planned next."
            ],
        )
