from typing import TYPE_CHECKING, Protocol

from openai import AsyncOpenAI
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

if TYPE_CHECKING:
    from app.core.config import Settings


class EmbeddingConfigurationError(ValueError):
    pass


class EmbeddingProviderError(RuntimeError):
    pass


class EmbeddingService(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass


class OpenAIEmbeddingService:
    def __init__(
        self,
        api_key: str,
        model: str,
        max_retries: int = 2,
        retry_initial_wait_seconds: float = 0.25,
        retry_max_wait_seconds: float = 2.0,
    ) -> None:
        if not api_key:
            raise EmbeddingConfigurationError("An API key is required for OpenAI embeddings.")
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
        self.max_retries = max_retries
        self.retry_initial_wait_seconds = retry_initial_wait_seconds
        self.retry_max_wait_seconds = retry_max_wait_seconds

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_retries + 1),
                wait=wait_exponential(
                    multiplier=self.retry_initial_wait_seconds,
                    max=self.retry_max_wait_seconds,
                ),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    response = await self.client.embeddings.create(model=self.model, input=texts)
        except Exception as exc:
            raise EmbeddingProviderError("OpenAI embedding generation failed.") from exc
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
        return OpenAIEmbeddingService(
            api_key=api_key,
            model=model,
            max_retries=settings.provider_max_retries,
            retry_initial_wait_seconds=settings.provider_retry_initial_wait_seconds,
            retry_max_wait_seconds=settings.provider_retry_max_wait_seconds,
        )

    raise EmbeddingConfigurationError(
        f"Unsupported embedding provider '{settings.embedding_provider}'."
    )
