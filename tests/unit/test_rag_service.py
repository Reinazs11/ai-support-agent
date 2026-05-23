import pytest

from app.core.config import Settings
from app.rag.chat_models import (
    INSUFFICIENT_CONTEXT_ANSWER,
    ChatModelProviderError,
    ChatModelResult,
)
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


class FakeChatModelService:
    model = "fake-chat-model"

    def __init__(
        self,
        answer: str = "Refunds are available within 30 days.",
        should_fail: bool = False,
    ) -> None:
        self.answer = answer
        self.should_fail = should_fail
        self.requests: list[tuple[str, list[RetrievedChunk]]] = []

    async def generate_answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
    ) -> ChatModelResult:
        self.requests.append((question, chunks))
        if self.should_fail:
            raise ChatModelProviderError("fake provider failed")
        return ChatModelResult(answer=self.answer, model=self.model)


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
async def test_chat_generates_answer_from_retrieved_chunks() -> None:
    result = RetrievedChunk(
        document_id="doc-1",
        chunk_id="chunk-1",
        chunk_index=0,
        filename="policy.txt",
        text="Refunds are available within 30 days.",
        score=0.92,
    )
    chat_model_service = FakeChatModelService()
    service = RagService(
        settings=Settings(retrieval_top_k=5),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(results=[result]),
        chat_model_service=chat_model_service,
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?", top_k=1))

    assert response.retrieval_status == "generated"
    assert response.confidence == "medium"
    assert len(response.sources) == 1
    assert response.sources[0].document_id == "doc-1"
    assert response.sources[0].chunk_id == "chunk-1"
    assert response.sources[0].title == "policy.txt"
    assert response.sources[0].score == 0.92
    assert response.answer == "Refunds are available within 30 days."
    assert chat_model_service.requests == [("What is the refund policy?", [result])]


@pytest.mark.asyncio
async def test_chat_limits_context_before_calling_llm() -> None:
    first = RetrievedChunk(
        document_id="doc-1",
        chunk_id="chunk-1",
        chunk_index=0,
        filename="policy.txt",
        text="Refunds are available within 30 days.",
        score=0.92,
    )
    second = RetrievedChunk(
        document_id="doc-2",
        chunk_id="chunk-2",
        chunk_index=0,
        filename="billing.txt",
        text="Billing disputes require support approval.",
        score=0.85,
    )
    chat_model_service = FakeChatModelService()
    service = RagService(
        settings=Settings(retrieval_top_k=5, rag_context_max_chars=11),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(results=[first, second]),
        chat_model_service=chat_model_service,
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.retrieval_status == "generated"
    assert len(response.sources) == 1
    assert response.sources[0].chunk_id == "chunk-1"
    assert chat_model_service.requests[0][1][0].text == "Refunds are"


@pytest.mark.asyncio
async def test_chat_falls_back_when_context_limit_excludes_empty_chunks() -> None:
    empty = RetrievedChunk(
        document_id="doc-1",
        chunk_id="chunk-1",
        chunk_index=0,
        filename="policy.txt",
        text="   ",
        score=0.92,
    )
    chat_model_service = FakeChatModelService()
    service = RagService(
        settings=Settings(retrieval_top_k=5, rag_context_max_chars=10),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(results=[empty]),
        chat_model_service=chat_model_service,
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.retrieval_status == "insufficient_context"
    assert response.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert response.sources == []
    assert chat_model_service.requests == []


@pytest.mark.asyncio
async def test_chat_reports_generation_not_configured_after_retrieval() -> None:
    result = RetrievedChunk(
        document_id="doc-1",
        chunk_id="chunk-1",
        chunk_index=0,
        filename="policy.txt",
        text="Refunds are available within 30 days.",
        score=0.92,
    )
    service = RagService(
        settings=Settings(chat_provider="disabled"),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(results=[result]),
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.retrieval_status == "generation_not_configured"
    assert response.confidence == "low"
    assert response.sources[0].chunk_id == "chunk-1"
    assert "LLM ainda nao esta configurada" in response.answer


@pytest.mark.asyncio
async def test_chat_reports_generation_failure_from_provider() -> None:
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
        chat_model_service=FakeChatModelService(should_fail=True),
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.retrieval_status == "generation_failed"
    assert response.confidence == "low"
    assert response.sources[0].chunk_id == "chunk-1"
    assert "provedor de LLM" in response.answer


@pytest.mark.asyncio
async def test_chat_marks_model_fallback_as_insufficient_context() -> None:
    result = RetrievedChunk(
        document_id="doc-1",
        chunk_id="chunk-1",
        chunk_index=0,
        filename="policy.txt",
        text="Refund policy summary without the requested exception.",
        score=0.7,
    )
    service = RagService(
        settings=Settings(retrieval_top_k=5),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(results=[result]),
        chat_model_service=FakeChatModelService(answer=INSUFFICIENT_CONTEXT_ANSWER),
    )

    response = await service.answer(ChatRequest(question="What exceptions apply?"))

    assert response.retrieval_status == "insufficient_context"
    assert response.confidence == "low"
    assert response.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert response.sources[0].chunk_id == "chunk-1"
