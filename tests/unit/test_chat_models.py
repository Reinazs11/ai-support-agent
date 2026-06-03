from app.core.config import Settings
from app.rag.chat_models import (
    ChatModelProviderError,
    OpenAIChatModelService,
    build_chat_model_service,
    build_grounded_messages,
)
from app.rag.vector_store import RetrievedChunk


class FakeChatMessage:
    content = "Refunds are available within 30 days."


class FakeChatChoice:
    message = FakeChatMessage()


class FakeChatUsage:
    prompt_tokens = 10
    completion_tokens = 8
    total_tokens = 18


class FakeChatResponse:
    choices = [FakeChatChoice()]
    usage = FakeChatUsage()


class FailingThenPassingCompletionsClient:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **kwargs: object) -> FakeChatResponse:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient")
        return FakeChatResponse()


class AlwaysFailingCompletionsClient:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **kwargs: object) -> FakeChatResponse:
        self.calls += 1
        raise RuntimeError("unavailable")


class FakeChatClient:
    def __init__(self, completions_client: object) -> None:
        self.completions = completions_client


class FakeOpenAIChatClient:
    def __init__(self, completions_client: object) -> None:
        self.chat = FakeChatClient(completions_client)


def test_build_chat_model_service_returns_none_when_disabled() -> None:
    settings = Settings(chat_provider="disabled")

    service = build_chat_model_service(settings)

    assert service is None


def test_build_chat_model_service_uses_generic_chat_key_for_openai() -> None:
    settings = Settings(
        chat_provider="openai",
        chat_api_key="test-key",
        chat_model="gpt-test",
    )

    service = build_chat_model_service(settings)

    assert isinstance(service, OpenAIChatModelService)
    assert service.model == "gpt-test"


def test_build_chat_model_service_keeps_openai_key_backward_compatibility() -> None:
    settings = Settings(
        chat_provider="openai",
        chat_api_key="",
        chat_model="",
        openai_api_key="test-key",
        openai_chat_model="gpt-4.1-mini",
    )

    service = build_chat_model_service(settings)

    assert isinstance(service, OpenAIChatModelService)
    assert service.model == "gpt-4.1-mini"


def test_grounded_prompt_contains_only_retrieved_chunks() -> None:
    chunks = [
        RetrievedChunk(
            document_id="doc-1",
            chunk_id="chunk-1",
            chunk_index=0,
            filename="policy.txt",
            text="Refunds are available within 30 days.",
            score=0.92,
        )
    ]

    messages = build_grounded_messages(
        question="What is the refund policy?",
        chunks=chunks,
    )

    prompt = "\n".join(message["content"] for message in messages)
    assert "Refunds are available within 30 days." in prompt
    assert "What is the refund policy?" in prompt
    assert "Always answer in English." in prompt
    assert "invented policy" not in prompt


async def test_openai_chat_model_service_retries_transient_failures() -> None:
    completions_client = FailingThenPassingCompletionsClient()
    service = OpenAIChatModelService(
        api_key="test-key",
        model="gpt-test",
        max_retries=1,
        retry_initial_wait_seconds=0,
        retry_max_wait_seconds=0,
    )
    service.client = FakeOpenAIChatClient(completions_client)  # type: ignore[assignment]

    result = await service.generate_answer(
        question="What is the refund policy?",
        chunks=[
            RetrievedChunk(
                document_id="doc-1",
                chunk_id="chunk-1",
                chunk_index=0,
                filename="policy.txt",
                text="Refunds are available within 30 days.",
                score=0.92,
            )
        ],
    )

    assert completions_client.calls == 2
    assert result.answer == "Refunds are available within 30 days."
    assert result.usage is not None
    assert result.usage.total_tokens == 18


async def test_openai_chat_model_service_reports_failure_after_retry_budget() -> None:
    completions_client = AlwaysFailingCompletionsClient()
    service = OpenAIChatModelService(
        api_key="test-key",
        model="gpt-test",
        max_retries=1,
        retry_initial_wait_seconds=0,
        retry_max_wait_seconds=0,
    )
    service.client = FakeOpenAIChatClient(completions_client)  # type: ignore[assignment]

    try:
        await service.generate_answer(
            question="What is the refund policy?",
            chunks=[
                RetrievedChunk(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    chunk_index=0,
                    filename="policy.txt",
                    text="Refunds are available within 30 days.",
                    score=0.92,
                )
            ],
        )
    except ChatModelProviderError:
        pass
    else:
        raise AssertionError("Expected chat provider failure.")

    assert completions_client.calls == 2
