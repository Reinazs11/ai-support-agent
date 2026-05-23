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


def test_qdrant_vector_store_searches_similar_chunks() -> None:
    store = QdrantVectorStore(url="unused", client=QdrantClient(":memory:"))
    collection_name = "test_search_collection"
    records = [
        ChunkVectorRecord(
            point_id="11111111-1111-1111-1111-111111111111",
            vector=[0.1, 0.2, 0.3],
            payload={
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "chunk_index": 0,
                "filename": "policy.txt",
                "text": "Refund policy",
            },
        ),
        ChunkVectorRecord(
            point_id="22222222-2222-2222-2222-222222222222",
            vector=[0.9, 0.1, 0.1],
            payload={
                "document_id": "doc-2",
                "chunk_id": "chunk-2",
                "chunk_index": 0,
                "filename": "pricing.txt",
                "text": "Pricing policy",
            },
        ),
    ]

    store.index_chunks(collection_name=collection_name, vector_size=3, records=records)

    results = store.search_similar(
        collection_name=collection_name,
        vector=[0.1, 0.2, 0.3],
        limit=1,
    )

    assert len(results) == 1
    assert results[0].document_id == "doc-1"
    assert results[0].chunk_id == "chunk-1"
    assert results[0].filename == "policy.txt"
    assert results[0].score > 0.9


def test_qdrant_vector_store_filters_search_by_document_ids() -> None:
    store = QdrantVectorStore(url="unused", client=QdrantClient(":memory:"))
    collection_name = "test_filtered_search_collection"
    records = [
        ChunkVectorRecord(
            point_id="11111111-1111-1111-1111-111111111111",
            vector=[0.1, 0.2, 0.3],
            payload={
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "chunk_index": 0,
                "filename": "policy.txt",
                "text": "Refund policy",
            },
        ),
        ChunkVectorRecord(
            point_id="22222222-2222-2222-2222-222222222222",
            vector=[0.1, 0.2, 0.3],
            payload={
                "document_id": "doc-2",
                "chunk_id": "chunk-2",
                "chunk_index": 0,
                "filename": "pricing.txt",
                "text": "Pricing policy",
            },
        ),
    ]

    store.index_chunks(collection_name=collection_name, vector_size=3, records=records)

    results = store.search_similar(
        collection_name=collection_name,
        vector=[0.1, 0.2, 0.3],
        limit=5,
        document_ids=["doc-2"],
    )

    assert len(results) == 1
    assert results[0].document_id == "doc-2"
    assert results[0].chunk_id == "chunk-2"
