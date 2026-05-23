from app.core.config import Settings
from app.rag.embeddings import OpenAIEmbeddingService, build_embedding_service


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
