import pytest

from app.core.config import Settings
from app.rag.schemas import ChatRequest
from app.rag.service import RagService
from app.rag.vector_store import ChunkVectorRecord, RetrievedChunk


class FakeEmbeddingService:
    def __init__(self, vectors: list[list[float]] | None = None) -> None:
        self.vectors = vectors or [[0.1, 0.2, 0.3]]
        self.requests: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.requests.append(texts)
        return self.vectors


class FakeVectorStore:
    def __init__(self, results: list[RetrievedChunk] | None = None) -> None:
        self.results = results or []
        self.search_limit: int | None = None
        self.search_vector: list[float] | None = None

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
        self.search_vector = vector
        self.search_limit = limit
        return self.results


@pytest.mark.asyncio
async def test_chat_reports_not_configured_without_embedding_service() -> None:
    service = RagService(settings=Settings(embedding_provider="disabled"))

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.retrieval_status == "not_configured"
    assert response.sources == []
    assert response.confidence == "low"


@pytest.mark.asyncio
async def test_chat_reports_no_results_when_vector_search_is_empty() -> None:
    embedding_service = FakeEmbeddingService()
    vector_store = FakeVectorStore()
    service = RagService(
        settings=Settings(retrieval_top_k=3),
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.retrieval_status == "no_results"
    assert response.sources == []
    assert vector_store.search_vector == [0.1, 0.2, 0.3]
    assert vector_store.search_limit == 3
    assert embedding_service.requests == [["What is the refund policy?"]]


@pytest.mark.asyncio
async def test_chat_returns_retrieved_sources_without_llm_generation() -> None:
    result = RetrievedChunk(
        document_id="doc-1",
        chunk_id="chunk-1",
        chunk_index=0,
        filename="policy.txt",
        text="Refunds are available within 30 days.",
        score=0.92,
    )
    service = RagService(
        settings=Settings(retrieval_top_k=5),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(results=[result]),
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?", top_k=1))

    assert response.retrieval_status == "retrieved"
    assert response.confidence == "medium"
    assert len(response.sources) == 1
    assert response.sources[0].document_id == "doc-1"
    assert response.sources[0].chunk_id == "chunk-1"
    assert response.sources[0].title == "policy.txt"
    assert response.sources[0].score == 0.92
    assert "geracao de resposta RAG" in response.answer
