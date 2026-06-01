from pathlib import Path
from uuid import uuid4

from anyio import Path as AsyncPath
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.documents.chunking import chunk_text
from app.documents.parsers import SUPPORTED_EXTENSIONS, parse_document
from app.documents.schemas import DocumentIngestResponse, DocumentUploadResponse
from app.rag.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    EmbeddingService,
    build_embedding_service,
)
from app.rag.vector_store import ChunkVectorRecord, QdrantVectorStore, VectorStore

INDEXING_UNAVAILABLE_WARNING = (
    "Embedding and Qdrant indexing were skipped because the configured embedding "
    "provider is unavailable or not configured."
)
INDEXING_FAILED_WARNING = (
    "Embedding or Qdrant indexing failed; chunks were persisted without vectors."
)


class DocumentNotFoundError(ValueError):
    pass


class DocumentTooLargeError(ValueError):
    pass


class UnsupportedDocumentTypeError(ValueError):
    pass


class DocumentService:
    def __init__(
        self,
        session: Session,
        upload_dir: Path | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        max_upload_mb: int | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        qdrant_collection: str | None = None,
        qdrant_vector_size: int | None = None,
    ) -> None:
        settings = get_settings()
        self.session = session
        self.upload_dir = upload_dir or Path(settings.upload_dir)
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
        self.max_upload_bytes = (max_upload_mb or settings.max_upload_mb) * 1024 * 1024
        self.qdrant_collection = qdrant_collection or settings.qdrant_collection
        self.qdrant_vector_size = qdrant_vector_size or settings.qdrant_vector_size
        self.embedding_service = embedding_service
        self.vector_store = vector_store

        if self.embedding_service is None:
            self.embedding_service = build_embedding_service(settings)
        if self.vector_store is None and self.embedding_service is not None:
            self.vector_store = QdrantVectorStore(url=settings.qdrant_url)

    async def register_upload(self, file: UploadFile) -> DocumentUploadResponse:
        filename = Path(file.filename or "uploaded-document").name
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise UnsupportedDocumentTypeError(
                f"Unsupported document type '{extension}'. Supported: {supported}"
            )

        document_id = str(uuid4())
        document_dir = self.upload_dir / document_id
        document_dir.mkdir(parents=True, exist_ok=True)
        storage_path = document_dir / filename
        size_bytes = await self._save_upload(file, storage_path)

        document = Document(
            id=document_id,
            filename=filename,
            content_type=file.content_type,
            storage_path=str(storage_path),
            size_bytes=size_bytes,
            status="registered",
        )
        self.session.add(document)
        self.session.commit()

        return DocumentUploadResponse(
            document_id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            status=document.status,
        )

    async def ingest(self, document_id: str) -> DocumentIngestResponse:
        document = self.session.get(Document, document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' was not found.")
        if document.storage_path is None:
            raise DocumentNotFoundError(f"Document '{document_id}' has no stored file.")

        path = Path(document.storage_path)
        if not await AsyncPath(document.storage_path).exists():
            document.status = "missing_file"
            self.session.commit()
            return DocumentIngestResponse(
                document_id=document_id,
                status=document.status,
                warnings=["Stored document file was not found on disk."],
            )

        text = parse_document(path)
        chunks = chunk_text(text, chunk_size=self.chunk_size, overlap=self.chunk_overlap)
        document.chunks.clear()
        for chunk in chunks:
            document.chunks.append(
                DocumentChunk(
                    id=str(uuid4()),
                    chunk_index=chunk.index,
                    text=chunk.text,
                    qdrant_point_id=None,
                )
            )

        vectors_indexed = 0
        warnings = []
        indexing_warning = None
        if chunks:
            vectors_indexed, indexing_warning = await self._index_document_chunks(document)
            document.status = "indexed" if vectors_indexed else "ingested"
        else:
            document.status = "ingested"
        self.session.commit()

        if not chunks:
            warnings.append("Document parsed successfully but no text chunks were produced.")
        if chunks and not vectors_indexed:
            warnings.append(indexing_warning or INDEXING_UNAVAILABLE_WARNING)

        return DocumentIngestResponse(
            document_id=document_id,
            status=document.status,
            chunks_indexed=len(chunks),
            vectors_indexed=vectors_indexed,
            warnings=warnings,
        )

    async def _save_upload(self, file: UploadFile, storage_path: Path) -> int:
        size_bytes = 0
        exceeded_limit = False
        with storage_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > self.max_upload_bytes:
                    exceeded_limit = True
                    break
                destination.write(chunk)
        if exceeded_limit:
            await AsyncPath(storage_path).unlink(missing_ok=True)
            raise DocumentTooLargeError(
                f"Uploaded document exceeds the {self.max_upload_bytes} byte limit."
            )
        return size_bytes

    async def _index_document_chunks(self, document: Document) -> tuple[int, str | None]:
        if self.embedding_service is None or self.vector_store is None:
            return 0, INDEXING_UNAVAILABLE_WARNING

        chunks = sorted(document.chunks, key=lambda chunk: chunk.chunk_index)
        try:
            vectors = await self.embedding_service.embed_texts([chunk.text for chunk in chunks])
        except EmbeddingConfigurationError:
            return 0, INDEXING_UNAVAILABLE_WARNING
        except EmbeddingProviderError:
            return 0, INDEXING_FAILED_WARNING

        if len(vectors) != len(chunks):
            return 0, INDEXING_FAILED_WARNING

        point_ids = [str(uuid4()) for _chunk in chunks]
        records = [
            ChunkVectorRecord(
                point_id=point_id,
                vector=vector,
                payload={
                    "document_id": document.id,
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "filename": document.filename,
                    "text": chunk.text,
                },
            )
            for chunk, vector, point_id in zip(chunks, vectors, point_ids, strict=True)
        ]
        try:
            self.vector_store.delete_document_vectors(
                collection_name=self.qdrant_collection,
                document_id=document.id,
            )
            self.vector_store.index_chunks(
                collection_name=self.qdrant_collection,
                vector_size=self.qdrant_vector_size,
                records=records,
            )
        except Exception:
            return 0, INDEXING_FAILED_WARNING

        for chunk, point_id in zip(chunks, point_ids, strict=True):
            chunk.qdrant_point_id = point_id
        return len(records), None
