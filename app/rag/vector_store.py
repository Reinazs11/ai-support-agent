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
    ) -> list[RetrievedChunk]:
        if not self.client.collection_exists(collection_name):
            return []

        response = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
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
