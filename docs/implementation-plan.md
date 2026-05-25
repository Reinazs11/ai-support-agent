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
index chunks in Qdrant when an embedding provider is configured. The first
provider is OpenAI, but settings now use a generic embedding provider layer so a
local provider can replace it later without changing the ingestion contract.
`/chat` can embed a question, retrieve top-k chunks from Qdrant, and return
source citations. LLM answer generation is still pending.

## Phase 4: RAG

- Implement retrieval top-k and metadata filtering.
- Compose grounded prompts and return answer plus citations.
- Add fallback when context is insufficient.
- Log retrieved documents, scores, latency, model, and token/cost estimates.

Status: started. `/chat` now retrieves top-k chunks, prompts a configurable chat
model with only those retrieved chunks, returns the generated answer plus source
citations, and falls back explicitly when no retrieved context is available.
Initial logging records top-k, model, source IDs/scores, and retrieval/generation
latency. Hardening increments added document ID filtering, a character-based
context limit before generation, context truncation logging, and controlled
handling for unexpected chat-provider errors. Chat responses now include token
usage when the provider returns it, and cost estimates when per-1M-token rates
are configured. Richer metadata filters, token-aware preflight budgeting, and
deeper provider retry behavior remain pending.

## Phase 5: Evaluation

- Create an initial dataset of 30 questions.
- Implement `scripts/run_eval.py` against the real chat service.
- Report answer correctness, correct source retrieval, fallback quality, cost, and latency.

Status: implemented. A 30-case JSONL dataset, synthetic eval corpus, public FTC
corpus snapshots, corpus seed script, and deterministic CLI runner are in place.
The runner calls the real `/chat` endpoint, checks expected answer substrings or
accepted variants, retrieval status, source titles, latency, and cost, then
writes JSON and Markdown reports with failure diagnostics for expected vs.
actual status, answer checks, and source titles. The English-only 30-case
dataset was calibrated with a local live run on 2026-05-24 and passed 30/30.
Deterministic answer checks now use normalized substring matching to reduce
punctuation, apostrophe, hyphen, whitespace, and casing false negatives. The
runner also reports deterministic answer-quality checks for canonical fallback
behavior, forbidden terms, and optional answer length limits. Future
LLM-as-judge or Ragas-style evaluation can be added after deterministic
regressions are stable.

## Phase 6: Agent And Workflows

- Add LangGraph state and nodes for direct answer, retrieval, ticket classification,
  escalation, ticket save, and email draft generation.
- Keep business actions simulated or human-approved by default.
- Add n8n webhook workflow after API behavior is stable.

## Phase 7: Observability And Deploy

- Integrate Langfuse traces around LLM calls and retrieval.
- Add deployment documentation and environment examples.
- Publish docs for known limitations, safety, and evaluation results.
