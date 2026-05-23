from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.rag.vector_store import RetrievedChunk

if TYPE_CHECKING:
    from app.core.config import Settings

INSUFFICIENT_CONTEXT_ANSWER = "Nao encontrei informacao suficiente para responder com seguranca."


class ChatModelConfigurationError(ValueError):
    pass


class ChatModelProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatModelResult:
    answer: str
    model: str


class ChatModelService(Protocol):
    model: str

    async def generate_answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
    ) -> ChatModelResult:
        pass


class OpenAIChatModelService:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ChatModelConfigurationError("An API key is required for OpenAI chat.")
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
    ) -> ChatModelResult:
        if not chunks:
            raise ChatModelProviderError("Cannot generate an answer without retrieved chunks.")

        messages = build_grounded_messages(question=question, chunks=chunks)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
            )
        except Exception as exc:
            raise ChatModelProviderError("OpenAI chat generation failed.") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise ChatModelProviderError("OpenAI returned an empty chat response.")

        return ChatModelResult(answer=content.strip(), model=self.model)


def build_grounded_messages(
    question: str,
    chunks: list[RetrievedChunk],
) -> list[ChatCompletionMessageParam]:
    context_blocks = "\n\n".join(
        (
            f"Source {index}\n"
            f"document_id: {chunk.document_id}\n"
            f"chunk_id: {chunk.chunk_id}\n"
            f"title: {chunk.filename}\n"
            f"text:\n{chunk.text}"
        )
        for index, chunk in enumerate(chunks, start=1)
    )
    return [
        cast(
            ChatCompletionMessageParam,
            {
                "role": "system",
                "content": (
                    "You are a support knowledge assistant. Answer only from the retrieved "
                    "source chunks in the user message. If the chunks do not contain enough "
                    f"information, answer exactly: {INSUFFICIENT_CONTEXT_ANSWER}"
                ),
            },
        ),
        cast(
            ChatCompletionMessageParam,
            {
                "role": "user",
                "content": (
                    "Retrieved source chunks:\n"
                    f"{context_blocks}\n\n"
                    f"Question:\n{question}"
                ),
            },
        ),
    ]


def build_chat_model_service(settings: "Settings") -> ChatModelService | None:
    if settings.chat_provider == "disabled":
        return None

    if settings.chat_provider == "openai":
        api_key = settings.chat_api_key or settings.openai_api_key
        model = settings.chat_model or settings.openai_chat_model
        if not api_key:
            return None
        return OpenAIChatModelService(api_key=api_key, model=model)

    raise ChatModelConfigurationError(f"Unsupported chat provider '{settings.chat_provider}'.")
