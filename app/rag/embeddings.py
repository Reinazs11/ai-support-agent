from typing import TYPE_CHECKING, Protocol

from openai import AsyncOpenAI

if TYPE_CHECKING:
    from app.core.config import Settings


class EmbeddingConfigurationError(ValueError):
    pass


class EmbeddingService(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass


class OpenAIEmbeddingService:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise EmbeddingConfigurationError("An API key is required for OpenAI embeddings.")
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = await self.client.embeddings.create(model=self.model, input=texts)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]


def build_embedding_service(settings: "Settings") -> EmbeddingService | None:
    if settings.embedding_provider == "disabled":
        return None

    if settings.embedding_provider == "local":
        # Local embeddings are intentionally not wired yet. Keeping this branch
        # explicit prevents the ingestion flow from being coupled to OpenAI only.
        return None

    if settings.embedding_provider == "openai":
        api_key = settings.embedding_api_key or settings.openai_api_key
        model = settings.embedding_model or settings.openai_embedding_model
        if not api_key:
            return None
        return OpenAIEmbeddingService(api_key=api_key, model=model)

    raise EmbeddingConfigurationError(
        f"Unsupported embedding provider '{settings.embedding_provider}'."
    )
