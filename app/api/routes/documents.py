from fastapi import APIRouter, File, UploadFile

from app.documents.schemas import DocumentIngestResponse, DocumentUploadResponse
from app.documents.service import DocumentService

router = APIRouter()


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    return await DocumentService().register_upload(file)


@router.post("/ingest/{document_id}", response_model=DocumentIngestResponse)
async def ingest_document(document_id: str) -> DocumentIngestResponse:
    return await DocumentService().ingest(document_id)
