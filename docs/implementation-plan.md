# Implementation Plan

## Phase 1: Foundation

- Create FastAPI app, settings, structured logging, Docker Compose, healthcheck,
  README, AGENTS.md, and basic tests.
- Add PostgreSQL and Qdrant services locally.
- Keep endpoint contracts stable but return explicit pending statuses where
  integrations are not ready yet.

## Phase 2: Persistence

- Add SQLAlchemy models for documents, chunks, tickets, chat sessions, messages,
  and evaluation runs.
- Configure Alembic and the first migration.
- Add integration tests for database connectivity and metadata writes.

Status: implemented in the Phase 2 branch with the initial schema migration and
SQLite-backed integration tests for model metadata writes. PostgreSQL migration
execution was validated locally with Docker Compose.

## Phase 3: Ingestion And Embeddings

- Persist uploaded files or normalized text.
- Parse `.pdf`, `.md`, `.txt`, and `.csv`.
- Chunk documents, generate embeddings, create Qdrant collection, and index chunks.
- Store chunk metadata in PostgreSQL with Qdrant point IDs.

Status: in progress. Uploaded files are stored locally, document metadata and
chunks are persisted in PostgreSQL, and ingestion can generate embeddings and
index chunks in Qdrant when `OPENAI_API_KEY` is configured.

## Phase 4: RAG

- Implement retrieval top-k and metadata filtering.
- Compose grounded prompts and return answer plus citations.
- Add fallback when context is insufficient.
- Log retrieved documents, scores, latency, model, and token/cost estimates.

## Phase 5: Evaluation

- Create an initial dataset of 30 questions.
- Implement `scripts/run_eval.py` against the real chat service.
- Report answer correctness, correct source retrieval, fallback quality, cost, and latency.

## Phase 6: Agent And Workflows

- Add LangGraph state and nodes for direct answer, retrieval, ticket classification,
  escalation, ticket save, and email draft generation.
- Keep business actions simulated or human-approved by default.
- Add n8n webhook workflow after API behavior is stable.

## Phase 7: Observability And Deploy

- Integrate Langfuse traces around LLM calls and retrieval.
- Add deployment documentation and environment examples.
- Publish docs for known limitations, safety, and evaluation results.
