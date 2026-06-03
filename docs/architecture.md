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
  route between RAG answers, ticket classification, internal ticket persistence,
  local email drafts, n8n webhook notifications, and human-approved business
  actions. n8n defaults to simulated mode and only dispatches live when an
  operator explicitly enables live mode, configures a webhook URL, and disables
  the human-approval blocker. Agent routing defaults to deterministic mode and
  can optionally use an LLM route classifier with deterministic fallback.
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
   counts, and estimated cost when cost rates are configured. Optional Langfuse
   tracing records content-minimized RAG spans for answer flow, embedding,
   vector search, context limiting, and generation.
8. Agent workflow logs record workflow run IDs, route, router provider/model,
   router rationale, router fallback reason, router latency, router token/cost
   estimates, action names/statuses, ticket IDs, approval-required flags, source
   counts, and workflow latency. They intentionally omit user message content,
   generated answers, retrieved context, and email draft bodies.
   Optional Langfuse tracing follows the same content-minimization rule for
   agent workflow and router spans.

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
- RAG context limiting uses a character budget plus an optional approximate
  token budget before provider calls. The token estimate is intentionally local
  and dependency-free; a model-specific tokenizer can replace it later if exact
  accounting becomes necessary.
- Cost estimates use configured per-1M-token rates instead of hardcoded pricing
  so the project can stay accurate as provider prices change.
- OpenAI embedding and chat calls use a small configurable retry/backoff policy.
  Final provider failures still return controlled API statuses instead of raw
  provider exceptions.
- Safety fallback is mandatory when there is insufficient retrieved context.
- Agent workflows should be measured with deterministic workflow evals before
  enabling live external automation such as n8n webhooks.
- Workflow audit logs should be structured and content-minimized before adding
  external side effects or richer tracing.
- Tracing is opt-in through `LANGFUSE_ENABLED=true` plus Langfuse credentials.
  Default local development and tests use a no-op tracer. Traces must not store
  full prompts, user messages, retrieved chunks, generated answers, webhook
  URLs, or email bodies.
- n8n integration defaults to a simulated action with a safe payload summary.
  Live dispatch uses the same minimized payload, timeout, retry settings, and
  content-minimized logs without recording the webhook URL or response body.
- LLM-assisted agent routing is opt-in. The deterministic router remains the
  default because it is cheaper, repeatable, and easier to evaluate. When LLM
  routing is enabled, provider/configuration/parse failures fall back to the
  deterministic router and are logged only as error-type metadata. Router usage
  and cost estimates use the same configurable chat token rates as RAG answer
  generation.
- Operationally, keep deterministic routing as the default for local
  development, baseline evals, and CI-like checks. Enable LLM routing only for
  demos or explicit experiments with ambiguous support requests, and keep n8n in
  simulated mode unless the run is specifically testing live webhook dispatch.
  The May 31, 2026 guarded LLM-router eval passed all 3 ambiguous ticket-like
  cases with `gpt-5.4-nano`, averaging 2223.24 ms, 437 total router tokens, and
  an estimated router cost of 0.00019765 USD. That is useful evidence, but the
  dataset is still too small to make LLM routing the default.
