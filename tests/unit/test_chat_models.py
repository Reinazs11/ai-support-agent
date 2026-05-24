from app.core.config import Settings
from app.rag.chat_models import (
    OpenAIChatModelService,
    build_chat_model_service,
    build_grounded_messages,
)
from app.rag.vector_store import RetrievedChunk


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
