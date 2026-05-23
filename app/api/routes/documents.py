from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.documents.schemas import DocumentIngestResponse, DocumentUploadResponse
from app.documents.service import (
    DocumentNotFoundError,
    DocumentService,
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
)

router = APIRouter()


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> DocumentUploadResponse:
    try:
        return await DocumentService(session).register_upload(file)
    except DocumentTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ingest/{document_id}", response_model=DocumentIngestResponse)
async def ingest_document(
    document_id: str,
    session: Session = Depends(get_db_session),
) -> DocumentIngestResponse:
    try:
        return await DocumentService(session).ingest(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
