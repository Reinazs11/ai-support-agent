from typing import Protocol

from openai import AsyncOpenAI


class EmbeddingConfigurationError(ValueError):
    pass


class EmbeddingService(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass


class OpenAIEmbeddingService:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise EmbeddingConfigurationError("OPENAI_API_KEY is required for embeddings.")
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = await self.client.embeddings.create(model=self.model, input=texts)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]
