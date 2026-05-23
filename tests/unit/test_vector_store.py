from qdrant_client import QdrantClient

from app.rag.vector_store import ChunkVectorRecord, QdrantVectorStore


def test_qdrant_vector_store_indexes_and_deletes_document_vectors() -> None:
    store = QdrantVectorStore(url="unused", client=QdrantClient(":memory:"))
    collection_name = "test_collection"
    record = ChunkVectorRecord(
        point_id="11111111-1111-1111-1111-111111111111",
        vector=[0.1, 0.2, 0.3],
        payload={
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "chunk_index": 0,
            "filename": "policy.txt",
            "text": "Refund policy",
        },
    )

    store.index_chunks(collection_name=collection_name, vector_size=3, records=[record])

    points, _next_page = store.client.scroll(collection_name=collection_name, with_payload=True)
    assert len(points) == 1
    assert points[0].payload["document_id"] == "doc-1"

    store.delete_document_vectors(collection_name=collection_name, document_id="doc-1")

    points, _next_page = store.client.scroll(collection_name=collection_name, with_payload=True)
    assert points == []
