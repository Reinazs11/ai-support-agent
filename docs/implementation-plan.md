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

Status: implemented for the portfolio baseline. Uploaded files are stored
locally, document metadata and chunks are persisted in PostgreSQL, and ingestion
can generate embeddings and index chunks in Qdrant when an embedding provider is
configured. The first provider is OpenAI, and settings use a generic embedding
provider layer so a local provider can replace it later without changing the
ingestion contract. Local embeddings remain reserved but not implemented.

## Phase 4: RAG

- Implement retrieval top-k and metadata filtering.
- Compose grounded prompts and return answer plus citations.
- Add fallback when context is insufficient.
- Log retrieved documents, scores, latency, model, and token/cost estimates.

Status: implemented for the portfolio baseline. `/chat` retrieves top-k chunks,
prompts a configurable chat model with only those retrieved chunks, returns the
generated answer plus source citations, and falls back explicitly when retrieved
context is unavailable or insufficient. Logging records top-k, model, source
IDs/scores, retrieval/generation latency, context truncation, token usage, and
estimated cost when rates are configured. Document ID filtering, character-based
context limits, and controlled provider-error handling are in place. Richer
metadata filters, token-aware preflight budgeting, and deeper provider retry
behavior remain possible hardening work, but they are not blockers for Phase 6.

## Phase 5: Evaluation

- Create an initial dataset of 30 questions.
- Implement `scripts/run_eval.py` against the real chat service.
- Report answer correctness, correct source retrieval, fallback quality, cost, and latency.

Status: implemented. A 30-case JSONL dataset, synthetic eval corpus, public FTC
corpus snapshots, corpus seed script, and CLI runner are in place. The runner
calls the real `/chat` endpoint, checks expected answer substrings or accepted
variants, retrieval status, source titles, latency, and cost, then writes JSON
and Markdown reports with failure diagnostics for expected vs. actual status,
answer checks, and source titles. The English-only 30-case dataset was
calibrated with a local live run on 2026-05-24 and passed 30/30. Deterministic
answer checks now use normalized substring matching to reduce punctuation,
apostrophe, hyphen, whitespace, and casing false negatives. The runner also
reports deterministic answer-quality checks for canonical fallback behavior,
forbidden terms, and optional answer length limits. An optional local semantic
heuristic judge can be enabled for softer answer-fact scoring without calling an
external provider; when enabled, it replaces deterministic substring matching as
the answer-correctness gate for generated-answer cases while keeping substring
results in reports for debugging. Retrieval status, source titles, fallback
behavior, forbidden terms, and length limits remain deterministic gates. This is
not a full semantic evaluation layer: it does not provide LLM-as-judge,
entailment checks, contradiction detection, or Ragas-style faithfulness metrics.
Those should wait until Phase 6 workflow behavior is stable enough to evaluate
against the right targets.

## Phase 6: Agent And Workflows

- Add LangGraph state and nodes for direct answer, retrieval, ticket classification,
  escalation, ticket save, and email draft generation.
- Keep business actions simulated or human-approved by default.
- Add n8n webhook workflow after API behavior is stable.

Status: in progress. `/agent/respond` routes between direct RAG answers and
deterministic ticket classification with LangGraph. Ticket workflows persist an
internal ticket record in PostgreSQL and generate local email drafts, while
email sending and high-priority escalation remain human-approval-required. No
external communication is sent automatically. A deterministic agent workflow
eval baseline covers ticket routes, ticket fields, action statuses, email-draft
approval, and forbidden completed external actions. Structured workflow audit
logs now record route, action names/statuses, ticket IDs, approval flags, source
counts, workflow run IDs, and latency without logging message or email body
content. Ticket workflows now include a simulated n8n webhook notification with
a safe payload summary; no outbound webhook request is sent. Real n8n dispatch
and LLM-assisted routing remain pending. The n8n dispatch boundary is now
explicit in settings: supported modes are `simulated` and `disabled`, URL
presence is logged only as a boolean, timeout/retry values are reserved, and
human approval remains required by default. Workflow logs also report explicit
network-dispatch blockers such as simulated mode, missing URL, and required
human approval. The agent eval runner can also
validate answer-mode disabled-provider behavior through
`evals/agent_answer_disabled.jsonl` and seeded-corpus answer behavior through
`evals/agent_answer_seeded.jsonl`, but optional answer datasets should be run
only when the local API configuration is known not to call live providers unless
explicitly desired.

Recommended next increments:

1. Add a real n8n dispatch implementation only after explicit approval,
   including the HTTP client, secret handling, retry/timeout behavior, and live
   integration test plan.
2. Consider LLM-assisted routing or real LLM-as-judge/Ragas only after the
   deterministic workflow baseline is stable.

## Phase 7: Observability And Deploy

- Integrate Langfuse traces around LLM calls and retrieval.
- Add deployment documentation and environment examples.
- Publish docs for known limitations, safety, and evaluation results.
