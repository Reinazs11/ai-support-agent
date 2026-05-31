from dataclasses import replace
from time import perf_counter

import structlog

from app.core.config import Settings, get_settings
from app.observability.tracing import Tracer, build_tracer
from app.rag.chat_models import (
    INSUFFICIENT_CONTEXT_ANSWER,
    ChatModelProviderError,
    ChatModelService,
    ChatTokenUsage,
    build_chat_model_service,
)
from app.rag.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    EmbeddingService,
    build_embedding_service,
)
from app.rag.schemas import ChatRequest, ChatResponse, ChatUsageEstimate, SourceCitation
from app.rag.vector_store import QdrantVectorStore, RetrievedChunk, VectorStore

logger = structlog.get_logger(__name__)


class RagService:
    def __init__(
        self,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        chat_model_service: ChatModelService | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or build_embedding_service(self.settings)
        self.vector_store = vector_store
        self.chat_model_service = chat_model_service or build_chat_model_service(self.settings)
        self.tracer = tracer or build_tracer(self.settings)
        if self.vector_store is None and self.embedding_service is not None:
            self.vector_store = QdrantVectorStore(url=self.settings.qdrant_url)

    async def answer(self, request: ChatRequest) -> ChatResponse:
        with self.tracer.span(
            "rag.answer",
            span_type="chain",
            metadata={
                "top_k": request.top_k or self.settings.retrieval_top_k,
                "document_filter_count": len(request.document_ids),
                "embedding_provider": self.settings.embedding_provider,
                "chat_provider": self.settings.chat_provider,
            },
        ) as span:
            response = await self._answer(request)
            span.update(
                output={
                    "retrieval_status": response.retrieval_status,
                    "confidence": response.confidence,
                    "source_count": len(response.sources),
                    "prompt_tokens": (
                        response.usage.prompt_tokens if response.usage is not None else None
                    ),
                    "completion_tokens": (
                        response.usage.completion_tokens
                        if response.usage is not None
                        else None
                    ),
                    "total_tokens": (
                        response.usage.total_tokens if response.usage is not None else None
                    ),
                    "estimated_cost_usd": (
                        response.usage.estimated_cost_usd
                        if response.usage is not None
                        else None
                    ),
                }
            )
            return response

    async def _answer(self, request: ChatRequest) -> ChatResponse:
        if self.embedding_service is None or self.vector_store is None:
            return ChatResponse(
                answer=(
                    "Vector search is not configured yet. Configure an embedding provider "
                    "and ingest documents before using RAG chat."
                ),
                sources=[],
                confidence="low",
                retrieval_status="not_configured",
            )

        try:
            with self.tracer.span(
                "rag.embedding",
                span_type="embedding",
                metadata={"embedding_provider": self.settings.embedding_provider},
            ) as span:
                question_vectors = await self.embedding_service.embed_texts(
                    [request.question]
                )
                span.update(output={"vector_count": len(question_vectors)})
        except EmbeddingConfigurationError as exc:
            self._log_embedding_unavailable(top_k=request.top_k, error_type=type(exc).__name__)
            return ChatResponse(
                answer=(
                    "Vector search cannot run because the embedding provider is not "
                    "configured correctly."
                ),
                sources=[],
                confidence="low",
                retrieval_status="embedding_unavailable",
            )
        except EmbeddingProviderError as exc:
            self._log_embedding_unavailable(top_k=request.top_k, error_type=type(exc).__name__)
            return ChatResponse(
                answer=(
                    "Vector search cannot run because the embedding provider is "
                    "currently unavailable."
                ),
                sources=[],
                confidence="low",
                retrieval_status="embedding_unavailable",
            )

        if not question_vectors:
            return ChatResponse(
                answer="Could not generate an embedding for the question.",
                sources=[],
                confidence="low",
                retrieval_status="embedding_unavailable",
            )

        top_k = request.top_k or self.settings.retrieval_top_k
        retrieval_started = perf_counter()
        with self.tracer.span(
            "rag.vector_search",
            span_type="retriever",
            metadata={
                "collection": self.settings.qdrant_collection,
                "top_k": top_k,
                "document_filter_count": len(request.document_ids),
            },
        ) as span:
            retrieved_chunks = self.vector_store.search_similar(
                collection_name=self.settings.qdrant_collection,
                vector=question_vectors[0],
                limit=top_k,
                document_ids=request.document_ids,
            )
            span.update(output={"retrieved_count": len(retrieved_chunks)})
        retrieval_latency_ms = (perf_counter() - retrieval_started) * 1000
        if not retrieved_chunks:
            self._log_chat_result(
                status="no_results",
                top_k=top_k,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=None,
                retrieved_count=0,
                context_source_count=0,
                context_chars=0,
                context_truncated=False,
            )
            return ChatResponse(
                answer=INSUFFICIENT_CONTEXT_ANSWER,
                sources=[],
                confidence="low",
                retrieval_status="no_results",
            )

        with self.tracer.span(
            "rag.context_limit",
            metadata={
                "retrieved_count": len(retrieved_chunks),
                "context_max_chars": self.settings.rag_context_max_chars,
            },
        ) as span:
            context_chunks, context_chars, context_truncated = self._limit_context_chunks(
                retrieved_chunks
            )
            span.update(
                output={
                    "context_source_count": len(context_chunks),
                    "context_chars": context_chars,
                    "context_truncated": context_truncated,
                }
            )
        if not context_chunks:
            self._log_chat_result(
                status="insufficient_context",
                top_k=top_k,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=None,
                retrieved_count=len(retrieved_chunks),
                context_source_count=0,
                context_chars=0,
                context_truncated=context_truncated,
            )
            return ChatResponse(
                answer=INSUFFICIENT_CONTEXT_ANSWER,
                sources=[],
                confidence="low",
                retrieval_status="insufficient_context",
            )

        sources = [
            SourceCitation(
                document_id=chunk.document_id,
                title=chunk.filename,
                chunk_id=chunk.chunk_id,
                score=chunk.score,
            )
            for chunk in context_chunks
        ]

        if self.chat_model_service is None:
            self._log_chat_result(
                status="generation_not_configured",
                top_k=top_k,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=None,
                retrieved_count=len(retrieved_chunks),
                context_source_count=len(sources),
                context_chars=context_chars,
                context_truncated=context_truncated,
                sources=sources,
            )
            return ChatResponse(
                answer=(
                    "Search found sources, but LLM answer generation is not configured yet."
                ),
                sources=sources,
                confidence="low",
                retrieval_status="generation_not_configured",
            )

        generation_started = perf_counter()
        try:
            with self.tracer.span(
                "rag.generation",
                span_type="generation",
                metadata={
                    "chat_provider": self.settings.chat_provider,
                    "chat_model": (
                        self.chat_model_service.model
                        or self.settings.chat_model
                        or self.settings.openai_chat_model
                    ),
                    "context_source_count": len(sources),
                    "context_chars": context_chars,
                    "context_truncated": context_truncated,
                },
            ) as span:
                model_result = await self.chat_model_service.generate_answer(
                    question=request.question,
                    chunks=context_chunks,
                )
                span.update(
                    output={
                        "model": model_result.model,
                        "prompt_tokens": (
                            model_result.usage.prompt_tokens
                            if model_result.usage is not None
                            else None
                        ),
                        "completion_tokens": (
                            model_result.usage.completion_tokens
                            if model_result.usage is not None
                            else None
                        ),
                        "total_tokens": (
                            model_result.usage.total_tokens
                            if model_result.usage is not None
                            else None
                        ),
                    }
                )
        except ChatModelProviderError as exc:
            generation_latency_ms = (perf_counter() - generation_started) * 1000
            self._log_chat_result(
                status="generation_failed",
                top_k=top_k,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=generation_latency_ms,
                retrieved_count=len(retrieved_chunks),
                context_source_count=len(sources),
                context_chars=context_chars,
                context_truncated=context_truncated,
                sources=sources,
                error_type=type(exc).__name__,
            )
            return ChatResponse(
                answer="Could not generate an answer with the configured LLM provider.",
                sources=sources,
                confidence="low",
                retrieval_status="generation_failed",
            )
        except Exception as exc:
            generation_latency_ms = (perf_counter() - generation_started) * 1000
            self._log_chat_result(
                status="generation_failed",
                top_k=top_k,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=generation_latency_ms,
                retrieved_count=len(retrieved_chunks),
                context_source_count=len(sources),
                context_chars=context_chars,
                context_truncated=context_truncated,
                sources=sources,
                error_type=type(exc).__name__,
            )
            return ChatResponse(
                answer="Could not generate an answer with the configured LLM provider.",
                sources=sources,
                confidence="low",
                retrieval_status="generation_failed",
            )

        generation_latency_ms = (perf_counter() - generation_started) * 1000
        usage_estimate = self._build_usage_estimate(model_result.usage)
        if model_result.answer == INSUFFICIENT_CONTEXT_ANSWER:
            self._log_chat_result(
                status="insufficient_context",
                top_k=top_k,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=generation_latency_ms,
                retrieved_count=len(retrieved_chunks),
                context_source_count=len(sources),
                context_chars=context_chars,
                context_truncated=context_truncated,
                sources=sources,
                model=model_result.model,
                usage=usage_estimate,
            )
            return ChatResponse(
                answer=model_result.answer,
                sources=sources,
                confidence="low",
                retrieval_status="insufficient_context",
                usage=usage_estimate,
            )

        self._log_chat_result(
            status="generated",
            top_k=top_k,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=generation_latency_ms,
            retrieved_count=len(retrieved_chunks),
            context_source_count=len(sources),
            context_chars=context_chars,
            context_truncated=context_truncated,
            sources=sources,
            model=model_result.model,
            usage=usage_estimate,
        )
        return ChatResponse(
            answer=model_result.answer,
            sources=sources,
            confidence="medium",
            retrieval_status="generated",
            usage=usage_estimate,
        )

    def _build_usage_estimate(self, usage: ChatTokenUsage | None) -> ChatUsageEstimate | None:
        if usage is None:
            return None

        estimated_cost_usd = self._estimate_chat_cost_usd(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
        return ChatUsageEstimate(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )

    def _estimate_chat_cost_usd(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float | None:
        prompt_rate = self.settings.chat_prompt_cost_per_1m_tokens
        completion_rate = self.settings.chat_completion_cost_per_1m_tokens
        if prompt_rate == 0 and completion_rate == 0:
            return None

        prompt_cost = (prompt_tokens / 1_000_000) * prompt_rate
        completion_cost = (completion_tokens / 1_000_000) * completion_rate
        return round(prompt_cost + completion_cost, 8)

    def _log_embedding_unavailable(
        self,
        *,
        top_k: int | None,
        error_type: str,
    ) -> None:
        self._log_chat_result(
            status="embedding_unavailable",
            top_k=top_k or self.settings.retrieval_top_k,
            retrieval_latency_ms=0,
            generation_latency_ms=None,
            retrieved_count=0,
            context_source_count=0,
            context_chars=0,
            context_truncated=False,
            error_type=error_type,
        )

    def _limit_context_chunks(
        self,
        retrieved_chunks: list[RetrievedChunk],
    ) -> tuple[list[RetrievedChunk], int, bool]:
        context_chunks: list[RetrievedChunk] = []
        context_chars = 0
        truncated = False
        max_chars = self.settings.rag_context_max_chars

        for chunk in retrieved_chunks:
            text = chunk.text.strip()
            if not text:
                truncated = True
                continue

            remaining_chars = max_chars - context_chars
            if remaining_chars <= 0:
                truncated = True
                break

            if len(text) > remaining_chars:
                text = text[:remaining_chars].rstrip()
                truncated = True

            if not text:
                break

            context_chunks.append(replace(chunk, text=text))
            context_chars += len(text)

        if len(context_chunks) < len(retrieved_chunks):
            truncated = True

        return context_chunks, context_chars, truncated

    def _log_chat_result(
        self,
        *,
        status: str,
        top_k: int,
        retrieval_latency_ms: float,
        generation_latency_ms: float | None,
        retrieved_count: int,
        context_source_count: int,
        context_chars: int,
        context_truncated: bool,
        sources: list[SourceCitation] | None = None,
        model: str | None = None,
        error_type: str | None = None,
        usage: ChatUsageEstimate | None = None,
    ) -> None:
        logger.info(
            "rag_chat_completed",
            retrieval_status=status,
            top_k=top_k,
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
            generation_latency_ms=(
                round(generation_latency_ms, 2) if generation_latency_ms is not None else None
            ),
            chat_provider=self.settings.chat_provider,
            chat_model=model or self.settings.chat_model or self.settings.openai_chat_model,
            retrieved_count=retrieved_count,
            context_source_count=context_source_count,
            context_chars=context_chars,
            context_max_chars=self.settings.rag_context_max_chars,
            context_truncated=context_truncated,
            error_type=error_type,
            prompt_tokens=usage.prompt_tokens if usage is not None else None,
            completion_tokens=usage.completion_tokens if usage is not None else None,
            total_tokens=usage.total_tokens if usage is not None else None,
            estimated_cost_usd=usage.estimated_cost_usd if usage is not None else None,
            sources=[
                {
                    "document_id": source.document_id,
                    "chunk_id": source.chunk_id,
                    "score": source.score,
                }
                for source in sources or []
            ],
        )
