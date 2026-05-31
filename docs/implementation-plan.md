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
context limits, and controlled provider-error handling are in place for chat and
embedding generation failures. Richer metadata filters, token-aware preflight
budgeting, and deeper provider retry behavior remain possible hardening work,
but they are not blockers for Phase 6.

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
ticket classification with LangGraph. The default route selector remains the
deterministic keyword/mode router so local development and baseline evals stay
cheap and repeatable. An optional LLM-assisted router can be enabled with
`AGENT_ROUTER_PROVIDER=llm`; it uses the configured OpenAI chat credentials and
model, asks only for a compact JSON route decision, and falls back explicitly to
the deterministic router when configuration, provider, or parse errors occur.
Ticket workflows persist an
internal ticket record in PostgreSQL and generate local email drafts, while
email sending and high-priority escalation remain human-approval-required. No
external communication is sent automatically. A deterministic agent workflow
eval baseline covers ticket routes, ticket fields, action statuses, email-draft
approval, and forbidden completed external actions. Structured workflow audit
logs now record route, action names/statuses, ticket IDs, approval flags, source
counts, router provider/model/rationale/fallback reason/latency, router
token/cost estimates, workflow run IDs, and workflow latency without logging
message or email body content. Ticket workflows now include an n8n webhook
notification boundary with a safe payload summary. It defaults to
simulated mode, but live mode can send a
real outbound POST when `N8N_WEBHOOK_MODE=live`, a webhook URL is configured,
and `N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=false`. LLM-assisted routing remains
opt-in rather than the baseline behavior. The n8n dispatch boundary is explicit
in settings: supported modes are
`simulated`, `disabled`, and `live`, URL presence is logged only as a boolean,
timeout/retry values are applied to live dispatch, and human approval remains
required by default. Workflow logs also report explicit network-dispatch
blockers such as simulated mode, missing URL, and required human approval.
Answer-mode agent paths now inherit controlled RAG provider failure responses,
so embedding provider outages return `embedding_unavailable` instead of an
unhandled API error. The
agent eval runner can also
validate answer-mode disabled-provider behavior through
`evals/agent_answer_disabled.jsonl` and seeded-corpus answer behavior through
`evals/agent_answer_seeded.jsonl`, but optional answer datasets should be run
only when the local API configuration is known not to call live providers unless
explicitly desired. The optional `evals/agent_router_llm.jsonl` dataset covers
ambiguous ticket-like auto-mode requests for the LLM router and is guarded by a
`/health` preflight that requires `dependencies.agent_router=llm`; its reports
aggregate router usage and estimated cost when the provider returns usage. A
guarded live run on May 31, 2026 passed all 3 LLM-router cases with
`gpt-5.4-nano`, averaging 2223.24 ms and 437 total router tokens for an
estimated 0.00019765 USD. This supports keeping the LLM router available for
explicit ambiguous-routing experiments, but the deterministic router remains the
default until broader answer-vs-ticket and negative-case eval coverage exists. A
controlled live n8n smoke test helper is also available; it checks `/health`
first and refuses to run unless n8n is fully `live`.

Recommended next increments:

1. Start Phase 7 observability/deploy work, beginning with traces around
   retrieval and LLM calls so future live router/RAG runs are easier to inspect.
2. Expand LLM-router eval coverage before considering it as a default route
   selector.
3. Consider real LLM-as-judge/Ragas only after the workflow targets are stable
   enough that the extra cost measures useful behavior.

## Phase 7: Observability And Deploy

- Integrate Langfuse traces around LLM calls and retrieval.
- Add deployment documentation and environment examples.
- Publish docs for known limitations, safety, and evaluation results.
