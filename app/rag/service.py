from app.core.config import Settings, get_settings
from app.rag.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingService,
    build_embedding_service,
)
from app.rag.schemas import ChatRequest, ChatResponse, SourceCitation
from app.rag.vector_store import QdrantVectorStore, VectorStore


class RagService:
    def __init__(
        self,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or build_embedding_service(self.settings)
        self.vector_store = vector_store
        if self.vector_store is None and self.embedding_service is not None:
            self.vector_store = QdrantVectorStore(url=self.settings.qdrant_url)

    async def answer(self, request: ChatRequest) -> ChatResponse:
        if self.embedding_service is None or self.vector_store is None:
            return ChatResponse(
                answer=(
                    "A busca vetorial ainda nao esta configurada. Configure um provedor de "
                    "embeddings e ingira documentos antes de usar o chat RAG."
                ),
                sources=[],
                confidence="low",
                retrieval_status="not_configured",
            )

        try:
            question_vectors = await self.embedding_service.embed_texts([request.question])
        except EmbeddingConfigurationError:
            return ChatResponse(
                answer=(
                    "A busca vetorial nao pode ser executada porque o provedor de embeddings "
                    "nao esta configurado corretamente."
                ),
                sources=[],
                confidence="low",
                retrieval_status="embedding_unavailable",
            )

        if not question_vectors:
            return ChatResponse(
                answer="Nao foi possivel gerar embedding para a pergunta.",
                sources=[],
                confidence="low",
                retrieval_status="embedding_unavailable",
            )

        top_k = request.top_k or self.settings.retrieval_top_k
        retrieved_chunks = self.vector_store.search_similar(
            collection_name=self.settings.qdrant_collection,
            vector=question_vectors[0],
            limit=top_k,
        )
        if not retrieved_chunks:
            return ChatResponse(
                answer=(
                    "Nao encontrei trechos relevantes na base vetorial para responder com "
                    "seguranca."
                ),
                sources=[],
                confidence="low",
                retrieval_status="no_results",
            )

        return ChatResponse(
            answer=(
                "Encontrei fontes relevantes na base vetorial, mas a geracao de resposta "
                "RAG com LLM ainda nao esta implementada."
            ),
            sources=[
                SourceCitation(
                    document_id=chunk.document_id,
                    title=chunk.filename,
                    chunk_id=chunk.chunk_id,
                    score=chunk.score,
                )
                for chunk in retrieved_chunks
            ],
            confidence="medium",
            retrieval_status="retrieved",
        )
