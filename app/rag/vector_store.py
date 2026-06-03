from dataclasses import dataclass
from typing import Any, Protocol

from qdrant_client import QdrantClient
from qdrant_client.http import models


@dataclass(frozen=True)
class ChunkVectorRecord:
    point_id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: str
    chunk_id: str
    chunk_index: int
    filename: str
    text: str
    score: float


@dataclass(frozen=True)
class VectorSearchFilter:
    document_ids: list[str] | None = None
    file_extensions: list[str] | None = None


class VectorStore(Protocol):
    def delete_document_vectors(self, collection_name: str, document_id: str) -> None:
        pass

    def index_chunks(
        self,
        collection_name: str,
        vector_size: int,
        records: list[ChunkVectorRecord],
    ) -> None:
        pass

    def search_similar(
        self,
        collection_name: str,
        vector: list[float],
        limit: int,
        document_ids: list[str] | None = None,
        metadata_filter: VectorSearchFilter | None = None,
    ) -> list[RetrievedChunk]:
        pass


class QdrantVectorStore:
    def __init__(self, url: str, client: QdrantClient | None = None) -> None:
        self.client = client or QdrantClient(url=url)

    def delete_document_vectors(self, collection_name: str, document_id: str) -> None:
        if not self.client.collection_exists(collection_name):
            return
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def index_chunks(
        self,
        collection_name: str,
        vector_size: int,
        records: list[ChunkVectorRecord],
    ) -> None:
        if not records:
            return
        self._ensure_collection(collection_name, vector_size)
        self.client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=record.point_id,
                    vector=record.vector,
                    payload=record.payload,
                )
                for record in records
            ],
        )

    def _ensure_collection(self, collection_name: str, vector_size: int) -> None:
        if self.client.collection_exists(collection_name):
            return
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    def search_similar(
        self,
        collection_name: str,
        vector: list[float],
        limit: int,
        document_ids: list[str] | None = None,
        metadata_filter: VectorSearchFilter | None = None,
    ) -> list[RetrievedChunk]:
        if not self.client.collection_exists(collection_name):
            return []

        query_filter = self._build_metadata_filter(
            document_ids=document_ids or [],
            metadata_filter=metadata_filter,
        )
        response = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            RetrievedChunk(
                document_id=str(point.payload.get("document_id", "")),
                chunk_id=str(point.payload.get("chunk_id", "")),
                chunk_index=int(point.payload.get("chunk_index", 0)),
                filename=str(point.payload.get("filename", "")),
                text=str(point.payload.get("text", "")),
                score=float(point.score),
            )
            for point in response.points
            if point.payload
        ]

    def _build_metadata_filter(
        self,
        *,
        document_ids: list[str],
        metadata_filter: VectorSearchFilter | None,
    ) -> models.Filter | None:
        requested_document_ids = list(document_ids)
        requested_file_extensions: list[str] = []
        if metadata_filter is not None:
            requested_document_ids.extend(metadata_filter.document_ids or [])
            requested_file_extensions.extend(metadata_filter.file_extensions or [])

        unique_document_ids = sorted({value for value in requested_document_ids if value})
        unique_file_extensions = sorted(
            {_normalize_file_extension(value) for value in requested_file_extensions if value}
        )

        conditions: list[models.FieldCondition] = []
        if unique_document_ids:
            conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=unique_document_ids),
                )
            )
        if unique_file_extensions:
            conditions.append(
                models.FieldCondition(
                    key="file_extension",
                    match=models.MatchAny(any=unique_file_extensions),
                )
            )

        if not conditions:
            return None

        return models.Filter(must=conditions)


def _normalize_file_extension(value: str) -> str:
    extension = value.strip().lower()
    if not extension:
        return extension
    if not extension.startswith("."):
        return f".{extension}"
    return extension
