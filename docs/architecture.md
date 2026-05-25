# Architecture

## Summary

The system is a production-style AI support agent. It ingests company documents,
chunks and embeds their content, stores vectors in Qdrant, persists operational
metadata in PostgreSQL, answers questions with grounded RAG, classifies support
tickets, and later executes controlled workflows with LangGraph.

## Components

- `api`: FastAPI routes and HTTP contracts.
- `core`: settings, logging, shared schemas, errors, and cross-cutting behavior.
- `db`: SQLAlchemy session, base models, and future migrations.
- `documents`: upload registration, parsing, normalization, chunking, and metadata.
- `rag`: embedding provider selection, Qdrant indexing, retrieval, prompt
  composition, and citations.
- `tickets`: deterministic first-pass classification and later LLM-assisted routing.
- `agents`: LangGraph state and controlled tools for Phase 6 workflows. These
  should route between RAG answers and simulated or human-approved business
  actions before any external side effects are enabled.
- `evals`: datasets, runners, metrics, and Markdown reports.
- `observability`: logs, latency spans, LLM traces, cost, and retrieved-document audit.

## Initial Data Flow

1. A user uploads a supported document.
2. The ingest flow parses content and creates chunks with metadata.
3. Embeddings are generated and stored in Qdrant.
4. Document and chunk metadata are stored in PostgreSQL.
5. `/chat` retrieves top-k chunks and builds a grounded prompt from only those
   chunks.
6. The configured chat model generates an answer, and the API returns citations
   for the sources actually retrieved.
7. Logs record top-k, retrieved count, context count, context size, truncation,
   source IDs and scores, model names, provider error type, latency, token
   counts, and estimated cost when cost rates are configured. Tracing is still
   planned.

## Key Decisions

- PostgreSQL stores source-of-truth metadata; Qdrant stores vector payloads optimized
  for semantic search.
- RAG should be implemented and evaluated before adding agentic routing.
- External providers must stay behind small services so tests can mock them.
- Embedding configuration is provider-based. OpenAI is the first implemented
  provider, and local embeddings are reserved as a future provider without
  changing document ingestion contracts.
- Chat model configuration is provider-based. OpenAI is the first implemented
  provider, and disabled mode keeps retrieval testable without LLM calls.
- RAG context limiting is currently character-based for simplicity. Token-aware
  budgeting can replace it once model-specific token counting is added before
  provider calls.
- Cost estimates use configured per-1M-token rates instead of hardcoded pricing
  so the project can stay accurate as provider prices change.
- Safety fallback is mandatory when there is insufficient retrieved context.
