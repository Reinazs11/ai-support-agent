import pytest

from app.core.config import Settings
from app.rag.chat_models import (
    INSUFFICIENT_CONTEXT_ANSWER,
    ChatModelProviderError,
    ChatModelResult,
    ChatTokenUsage,
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
        self.search_document_ids: list[str] | None = None

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
    ) -> list[RetrievedChunk]:
        self.search_vector = vector
        self.search_limit = limit
        self.search_document_ids = document_ids
        return self.results


class FakeChatModelService:
    model = "fake-chat-model"

    def __init__(
        self,
        answer: str = "Refunds are available within 30 days.",
        should_fail: bool = False,
        unexpected_exception: Exception | None = None,
        usage: ChatTokenUsage | None = None,
    ) -> None:
        self.answer = answer
        self.should_fail = should_fail
        self.unexpected_exception = unexpected_exception
        self.usage = usage
        self.requests: list[tuple[str, list[RetrievedChunk]]] = []

    async def generate_answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
    ) -> ChatModelResult:
        self.requests.append((question, chunks))
        if self.should_fail:
            raise ChatModelProviderError("fake provider failed")
        if self.unexpected_exception is not None:
            raise self.unexpected_exception
        return ChatModelResult(answer=self.answer, model=self.model, usage=self.usage)


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
    assert vector_store.search_document_ids == []
    assert embedding_service.requests == [["What is the refund policy?"]]


@pytest.mark.asyncio
async def test_chat_passes_document_ids_to_vector_search() -> None:
    embedding_service = FakeEmbeddingService()
    vector_store = FakeVectorStore()
    service = RagService(
        settings=Settings(retrieval_top_k=3),
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    response = await service.answer(
        ChatRequest(question="What is the refund policy?", document_ids=["doc-1", "doc-2"])
    )

    assert response.retrieval_status == "no_results"
    assert vector_store.search_document_ids == ["doc-1", "doc-2"]


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
    assert response.usage is None
    assert chat_model_service.requests == [("What is the refund policy?", [result])]


@pytest.mark.asyncio
async def test_chat_returns_token_usage_and_cost_estimate() -> None:
    result = RetrievedChunk(
        document_id="doc-1",
        chunk_id="chunk-1",
        chunk_index=0,
        filename="policy.txt",
        text="Refunds are available within 30 days.",
        score=0.92,
    )
    service = RagService(
        settings=Settings(
            retrieval_top_k=5,
            chat_prompt_cost_per_1m_tokens=0.50,
            chat_completion_cost_per_1m_tokens=1.50,
        ),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(results=[result]),
        chat_model_service=FakeChatModelService(
            usage=ChatTokenUsage(prompt_tokens=1000, completion_tokens=200, total_tokens=1200)
        ),
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.retrieval_status == "generated"
    assert response.usage is not None
    assert response.usage.prompt_tokens == 1000
    assert response.usage.completion_tokens == 200
    assert response.usage.total_tokens == 1200
    assert response.usage.estimated_cost_usd == 0.0008


@pytest.mark.asyncio
async def test_chat_returns_token_usage_without_cost_when_rates_are_unset() -> None:
    result = RetrievedChunk(
        document_id="doc-1",
        chunk_id="chunk-1",
        chunk_index=0,
        filename="policy.txt",
        text="Refunds are available within 30 days.",
        score=0.92,
    )
    service = RagService(
        settings=Settings(
            retrieval_top_k=5,
            chat_prompt_cost_per_1m_tokens=0,
            chat_completion_cost_per_1m_tokens=0,
        ),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(results=[result]),
        chat_model_service=FakeChatModelService(
            usage=ChatTokenUsage(prompt_tokens=1000, completion_tokens=200, total_tokens=1200)
        ),
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.usage is not None
    assert response.usage.estimated_cost_usd is None


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
    assert "LLM answer generation is not configured yet" in response.answer


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
    assert "configured LLM provider" in response.answer


@pytest.mark.asyncio
async def test_chat_reports_unexpected_generation_failure_from_provider() -> None:
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
        chat_model_service=FakeChatModelService(unexpected_exception=RuntimeError("boom")),
    )

    response = await service.answer(ChatRequest(question="What is the refund policy?"))

    assert response.retrieval_status == "generation_failed"
    assert response.confidence == "low"
    assert response.sources[0].chunk_id == "chunk-1"
    assert "configured LLM provider" in response.answer


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
