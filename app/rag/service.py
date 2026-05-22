from app.rag.schemas import ChatRequest, ChatResponse


class RagService:
    async def answer(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            answer=(
                "Ainda nao ha uma base vetorial indexada. Ingira documentos antes de usar "
                "o chat RAG."
            ),
            sources=[],
            confidence="low",
            retrieval_status="pending_qdrant_integration",
        )
