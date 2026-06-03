# Implementation Plan

This file tracks the project roadmap at a high level. Detailed behavior lives in
the focused docs linked from the README.

## Phase 1: Foundation

Status: implemented.

- FastAPI application structure.
- Environment-based settings.
- Structured JSON logging.
- Docker Compose for local PostgreSQL and Qdrant.
- `/health` contract and initial tests.

## Phase 2: Persistence

Status: implemented.

- SQLAlchemy models for documents, chunks, tickets, chat/eval metadata.
- Alembic setup and initial migrations.
- Integration tests for metadata persistence.

## Phase 3: Ingestion And Embeddings

Status: implemented for portfolio baseline.

- Upload registration and local file storage.
- Parsing for `.pdf`, `.md`, `.txt`, and `.csv`.
- Chunk persistence in PostgreSQL.
- OpenAI embedding provider and Qdrant indexing.
- Local embedding provider remains reserved but not implemented.

## Phase 4: RAG

Status: implemented for portfolio baseline.

- `/chat` retrieves top-k chunks from Qdrant.
- Prompt construction uses only retrieved chunks.
- Responses include answer, confidence, retrieval status, usage, and citations.
- Controlled fallbacks cover missing vector search, no results, insufficient
  context, provider configuration failures, and provider runtime failures.
- Logging covers latency, model, top-k, context limits, token usage, estimated
  cost, and source IDs without logging full prompts or documents.

Known hardening left for production: broader metadata filters, model-specific
token budgeting, and retry/backoff policy.

## Phase 5: Evaluation

Status: implemented.

- 30-case RAG dataset with synthetic and public FTC-source corpus snapshots.
- Corpus seed script and `/chat` eval runner.
- JSON and Markdown reports under `reports/evals/`.
- Deterministic answer/source/fallback checks.
- Optional local heuristic semantic judge for low-cost paraphrase tolerance.

The heuristic judge is not LLM-as-judge or Ragas. It is a regression aid, not a
production semantic evaluation layer.

## Phase 6: Agent And Workflows

Status: implemented for controlled workflow baseline.

- `/agent/respond` routes between RAG answer mode and ticket workflow mode.
- LangGraph workflow for ticket classification, save, email draft, n8n
  notification boundary, and human escalation.
- Deterministic router is the default.
- Optional LLM-router is available behind `AGENT_ROUTER_PROVIDER=llm` and falls
  back to deterministic routing on provider/configuration/parse errors.
- n8n defaults to `simulated`; live dispatch requires explicit live mode,
  configured URL, and human-approval blocker removal.
- Agent evals cover ticket workflow behavior, answer-path fallback contracts,
  seeded answer mode, and optional guarded LLM-router checks.

Current operating decision: deterministic routing remains the default. The
guarded LLM-router live eval passed 3/3 ambiguous ticket-like cases on
May 31, 2026, but the dataset is still too small to make LLM routing the
baseline.

## Phase 7: Observability And Deploy

Status: implemented for demo readiness.

- Optional content-minimized Langfuse tracing with no-op default.
- RAG spans cover answer flow, embedding, vector search, context limiting, and
  generation.
- Agent spans cover workflow execution and router decisions.
- Traces record statuses, counts, model names, token usage, cost estimates, and
  operational IDs.
- Deployment readiness doc defines services, env groups, startup order,
  `/health` expectations, safe demo defaults, and non-production gaps.
- Docker image includes Alembic migration assets.
- Demo guide defines a safe portfolio/interview walkthrough.

Remaining production work: authentication, authorization, rate limiting, object
storage, retention policy, platform-specific deployment, secret manager
integration, deep readiness checks, observability dashboard setup, and sampling
policy.

## Phase 8: Portfolio Enrichment

Status: started.

These are targeted improvements to make the project stronger against entry-level
AI Engineer job requirements. They are not required for the local portfolio
baseline, but they add interview-ready evidence around production LLM
engineering, deployment, evaluation, and applied ML trade-offs.

Recommended increments:

- Harden RAG with richer metadata filters, token-aware context budgeting, and
  retry/backoff behavior for provider calls.
- Add optional LLM-as-judge or Ragas-style evaluation with explicit cost guards
  and report output.
- Add basic API-key authentication, authorization boundaries, and rate limiting.
- Add deep readiness checks for PostgreSQL and Qdrant.
- Add a platform-specific public deployment guide and, when practical, deploy a
  private or public demo.
- Add an observability dashboard or queryable audit view for latency, costs,
  retrieval status, and workflow outcomes.
- Consider a separate small MLOps project for scikit-learn/PyTorch, MLflow, and
  model-training workflows instead of forcing classic ML tooling into this RAG
  backend.
- Consider a separate MCP or LangChain/LlamaIndex adapter demo if job-search
  positioning needs those keywords, while keeping this core backend simple.

Current implementation focus: start with RAG hardening because it strengthens
the existing architecture directly and maps cleanly to common job posting
requirements for RAG systems with metadata filtering, evaluation, and operational
reliability.

Progress:

- Metadata filtering started with an explicit `/chat` `metadata_filter` request
  object supporting document IDs and file extensions. New indexed chunks now
  include `file_extension` payload metadata for Qdrant filtering.
- Context budgeting now supports an optional approximate `RAG_CONTEXT_MAX_TOKENS`
  guard in addition to `RAG_CONTEXT_MAX_CHARS`, so retrieved context is bounded
  before chat generation without adding a tokenizer dependency.
- OpenAI embedding and chat provider calls now use a configurable retry/backoff
  policy before returning controlled provider-failure statuses.
