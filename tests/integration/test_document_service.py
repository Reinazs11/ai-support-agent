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
    INDEXING_FAILED_WARNING,
    INDEXING_UNAVAILABLE_WARNING,
    DocumentService,
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
)
from app.rag.embeddings import EmbeddingProviderError
from app.rag.vector_store import ChunkVectorRecord


class FakeEmbeddingService:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), 0.1, 0.2] for index, _text in enumerate(texts)]


class FailingEmbeddingService:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingProviderError("fake embedding provider failure")


class FakeVectorStore:
    def __init__(self, *, fail_on_index: bool = False) -> None:
        self.deleted_document_ids: list[str] = []
        self.indexed_records: list[ChunkVectorRecord] = []
        self.collection_name: str | None = None
        self.vector_size: int | None = None
        self.fail_on_index = fail_on_index

    def delete_document_vectors(self, collection_name: str, document_id: str) -> None:
        self.collection_name = collection_name
        self.deleted_document_ids.append(document_id)

    def index_chunks(
        self,
        collection_name: str,
        vector_size: int,
        records: list[ChunkVectorRecord],
    ) -> None:
        if self.fail_on_index:
            raise RuntimeError("fake Qdrant indexing failure")
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.indexed_records.extend(records)


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
        select(DocumentChunk)
        .where(DocumentChunk.document_id == upload.document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    document = session.get(Document, upload.document_id)
    assert document is not None
    assert document.status == "ingested"
    assert response.status == "ingested"
    assert response.chunks_indexed == len(chunks)
    assert response.vectors_indexed == 0
    assert response.warnings == [INDEXING_UNAVAILABLE_WARNING]
    assert len(chunks) > 1
    assert all(chunk.qdrant_point_id is None for chunk in chunks)


@pytest.mark.asyncio
async def test_ingest_indexes_chunks_with_configured_services(tmp_path) -> None:
    session = build_test_session()
    vector_store = FakeVectorStore()
    service = DocumentService(
        session,
        upload_dir=tmp_path,
        chunk_size=20,
        chunk_overlap=5,
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        qdrant_collection="test_knowledge",
        qdrant_vector_size=3,
    )
    upload = await service.register_upload(
        build_upload("policy.txt", b"Refunds are available within 30 days.")
    )

    response = await service.ingest(upload.document_id)

    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == upload.document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    document = session.get(Document, upload.document_id)
    assert document is not None
    assert document.status == "indexed"
    assert response.status == "indexed"
    assert response.chunks_indexed == len(chunks)
    assert response.vectors_indexed == len(chunks)
    assert response.warnings == []
    assert vector_store.collection_name == "test_knowledge"
    assert vector_store.vector_size == 3
    assert vector_store.deleted_document_ids == [upload.document_id]
    assert len(vector_store.indexed_records) == len(chunks)
    assert all(chunk.qdrant_point_id is not None for chunk in chunks)
    assert [chunk.qdrant_point_id for chunk in chunks] == [
        record.point_id for record in vector_store.indexed_records
    ]


@pytest.mark.asyncio
async def test_ingest_keeps_chunks_without_vectors_when_embedding_provider_fails(tmp_path) -> None:
    session = build_test_session()
    service = DocumentService(
        session,
        upload_dir=tmp_path,
        chunk_size=20,
        chunk_overlap=5,
        embedding_service=FailingEmbeddingService(),
        vector_store=FakeVectorStore(),
    )
    upload = await service.register_upload(
        build_upload("policy.txt", b"Refunds are available within 30 days.")
    )

    response = await service.ingest(upload.document_id)

    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == upload.document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    document = session.get(Document, upload.document_id)
    assert document is not None
    assert document.status == "ingested"
    assert response.status == "ingested"
    assert response.chunks_indexed == len(chunks)
    assert response.vectors_indexed == 0
    assert response.warnings == [INDEXING_FAILED_WARNING]
    assert all(chunk.qdrant_point_id is None for chunk in chunks)


@pytest.mark.asyncio
async def test_ingest_keeps_chunks_without_vectors_when_qdrant_indexing_fails(tmp_path) -> None:
    session = build_test_session()
    vector_store = FakeVectorStore(fail_on_index=True)
    service = DocumentService(
        session,
        upload_dir=tmp_path,
        chunk_size=20,
        chunk_overlap=5,
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
    )
    upload = await service.register_upload(
        build_upload("policy.txt", b"Refunds are available within 30 days.")
    )

    response = await service.ingest(upload.document_id)

    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == upload.document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    document = session.get(Document, upload.document_id)
    assert document is not None
    assert document.status == "ingested"
    assert response.status == "ingested"
    assert response.chunks_indexed == len(chunks)
    assert response.vectors_indexed == 0
    assert response.warnings == [INDEXING_FAILED_WARNING]
    assert vector_store.deleted_document_ids == [upload.document_id]
    assert vector_store.indexed_records == []
    assert all(chunk.qdrant_point_id is None for chunk in chunks)


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
