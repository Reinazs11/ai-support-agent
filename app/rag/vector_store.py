from dataclasses import dataclass
from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.http import models


@dataclass(frozen=True)
class ChunkVectorRecord:
    point_id: str
    vector: list[float]
    payload: dict[str, str | int | float | None]


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
