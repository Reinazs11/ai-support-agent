from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.db.base import Base
from app.db.models import Document, DocumentChunk
from app.db.session import create_session_factory
from app.documents.service import (
    DocumentService,
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
)


def build_test_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


def build_upload(filename: str, content: bytes, content_type: str = "text/plain") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers={"content-type": content_type},
    )


@pytest.mark.asyncio
async def test_register_upload_persists_file_and_metadata(tmp_path) -> None:
    session = build_test_session()
    service = DocumentService(session, upload_dir=tmp_path)

    response = await service.register_upload(
        build_upload("policy.txt", b"Refunds are available within 30 days.")
    )

    document = session.get(Document, response.document_id)
    assert document is not None
    assert document.filename == "policy.txt"
    assert document.size_bytes == 37
    assert document.storage_path is not None
    assert tmp_path in Path(document.storage_path).parents
    assert document.status == "registered"


@pytest.mark.asyncio
async def test_ingest_parses_and_persists_chunks(tmp_path) -> None:
    session = build_test_session()
    service = DocumentService(session, upload_dir=tmp_path, chunk_size=20, chunk_overlap=5)
    upload = await service.register_upload(
        build_upload("policy.txt", b"Refunds are available within 30 days.")
    )

    response = await service.ingest(upload.document_id)

    chunks = session.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == upload.document_id)
    ).all()
    document = session.get(Document, upload.document_id)
    assert document is not None
    assert document.status == "ingested"
    assert response.status == "ingested"
    assert response.chunks_indexed == len(chunks)
    assert len(chunks) > 1


@pytest.mark.asyncio
async def test_register_upload_rejects_unsupported_file_type(tmp_path) -> None:
    session = build_test_session()
    service = DocumentService(session, upload_dir=tmp_path)

    with pytest.raises(UnsupportedDocumentTypeError):
        await service.register_upload(build_upload("malware.exe", b"nope"))


@pytest.mark.asyncio
async def test_register_upload_rejects_oversized_file(tmp_path) -> None:
    session = build_test_session()
    service = DocumentService(session, upload_dir=tmp_path, max_upload_mb=1)

    with pytest.raises(DocumentTooLargeError):
        await service.register_upload(build_upload("large.txt", b"x" * ((1024 * 1024) + 1)))
