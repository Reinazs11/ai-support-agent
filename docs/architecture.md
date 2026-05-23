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
- `agents`: LangGraph state and controlled tools after the RAG path is validated.
- `evals`: datasets, runners, metrics, and Markdown reports.
- `observability`: logs, latency spans, LLM traces, cost, and retrieved-document audit.

## Initial Data Flow

1. A user uploads a supported document.
2. The ingest flow parses content and creates chunks with metadata.
3. Embeddings are generated and stored in Qdrant.
4. Document and chunk metadata are stored in PostgreSQL.
5. `/chat` retrieves top-k chunks, builds a grounded prompt, and returns an answer
   with only the sources actually retrieved.
6. Logs and traces record request IDs, retrieval inputs, model names, latency, and cost.

## Key Decisions

- PostgreSQL stores source-of-truth metadata; Qdrant stores vector payloads optimized
  for semantic search.
- RAG should be implemented and evaluated before adding agentic routing.
- External providers must stay behind small services so tests can mock them.
- Embedding configuration is provider-based. OpenAI is the first implemented
  provider, and local embeddings are reserved as a future provider without
  changing document ingestion contracts.
- Safety fallback is mandatory when there is insufficient retrieved context.
