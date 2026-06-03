from app.core.config import Settings
from app.rag.embeddings import (
    EmbeddingProviderError,
    OpenAIEmbeddingService,
    build_embedding_service,
)


class FakeEmbeddingItem:
    def __init__(self, index: int, embedding: list[float]) -> None:
        self.index = index
        self.embedding = embedding


class FakeEmbeddingResponse:
    def __init__(self) -> None:
        self.data = [
            FakeEmbeddingItem(index=1, embedding=[0.2, 0.3]),
            FakeEmbeddingItem(index=0, embedding=[0.1, 0.2]),
        ]


class FailingThenPassingEmbeddingsClient:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **kwargs: object) -> FakeEmbeddingResponse:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient")
        return FakeEmbeddingResponse()


class AlwaysFailingEmbeddingsClient:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **kwargs: object) -> FakeEmbeddingResponse:
        self.calls += 1
        raise RuntimeError("unavailable")


class FakeOpenAIEmbeddingClient:
    def __init__(self, embeddings_client: object) -> None:
        self.embeddings = embeddings_client


def test_build_embedding_service_returns_none_when_disabled() -> None:
    settings = Settings(embedding_provider="disabled")

    service = build_embedding_service(settings)

    assert service is None


def test_build_embedding_service_returns_none_for_local_until_implemented() -> None:
    settings = Settings(embedding_provider="local")

    service = build_embedding_service(settings)

    assert service is None


def test_build_embedding_service_uses_generic_embedding_key_for_openai() -> None:
    settings = Settings(
        embedding_provider="openai",
        embedding_api_key="test-key",
        embedding_model="text-embedding-3-small",
        openai_api_key="",
    )

    service = build_embedding_service(settings)

    assert isinstance(service, OpenAIEmbeddingService)
    assert service.model == "text-embedding-3-small"


async def test_openai_embedding_service_retries_transient_failures() -> None:
    embeddings_client = FailingThenPassingEmbeddingsClient()
    service = OpenAIEmbeddingService(
        api_key="test-key",
        model="text-embedding-3-small",
        max_retries=1,
        retry_initial_wait_seconds=0,
        retry_max_wait_seconds=0,
    )
    service.client = FakeOpenAIEmbeddingClient(embeddings_client)  # type: ignore[assignment]

    vectors = await service.embed_texts(["first", "second"])

    assert embeddings_client.calls == 2
    assert vectors == [[0.1, 0.2], [0.2, 0.3]]


async def test_openai_embedding_service_reports_failure_after_retry_budget() -> None:
    embeddings_client = AlwaysFailingEmbeddingsClient()
    service = OpenAIEmbeddingService(
        api_key="test-key",
        model="text-embedding-3-small",
        max_retries=1,
        retry_initial_wait_seconds=0,
        retry_max_wait_seconds=0,
    )
    service.client = FakeOpenAIEmbeddingClient(embeddings_client)  # type: ignore[assignment]

    try:
        await service.embed_texts(["first"])
    except EmbeddingProviderError:
        pass
    else:
        raise AssertionError("Expected embedding provider failure.")

    assert embeddings_client.calls == 2


def test_build_embedding_service_keeps_openai_key_backward_compatibility() -> None:
    settings = Settings(
        embedding_provider="openai",
        embedding_api_key="",
        embedding_model="",
        openai_api_key="test-key",
        openai_embedding_model="text-embedding-3-small",
    )

    service = build_embedding_service(settings)

    assert isinstance(service, OpenAIEmbeddingService)
    assert service.model == "text-embedding-3-small"
