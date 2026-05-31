# AI Support & Knowledge Agent

A production-style AI Engineering portfolio project for building a support and
knowledge-base agent with document ingestion, RAG, vector search, evaluation,
observability, and controlled agentic workflows.

The goal is not to hide complexity behind a demo. The goal is to build the system
incrementally, with clear backend architecture, explicit contracts, measurable
quality, and honest documentation about what is complete and what is still planned.

## What This Project Will Support

- Document ingestion for company knowledge-base files.
- Parsing and chunking for `.pdf`, `.md`, `.txt`, and `.csv`.
- Embedding generation for semantic search.
- Vector storage in Qdrant.
- Metadata storage in PostgreSQL.
- RAG-based question answering with real sources and citations.
- Ticket or lead classification.
- Controlled agent workflows with human-in-the-loop boundaries.
- Automated RAG evaluation.
- Structured logs, latency tracking, cost tracking, and LLM tracing.
- Local execution with Docker Compose.
- Public deployment and demo documentation.

## Current Status

Phase 1 foundation, Phase 2 persistence, Phase 3 ingestion/indexing/retrieval,
Phase 4 RAG answer generation, and Phase 5 evaluation are in place. Phase 6
agent workflows are in progress.

Implemented:

- FastAPI application structure.
- Environment-based settings.
- Structured logging setup.
- Initial HTTP contracts.
- Document upload metadata persistence and document chunk persistence.
- Embedding and Qdrant indexing path when an embedding provider is configured.
- Initial embedding provider configuration for OpenAI, future local models, or disabled mode.
- Retrieval from Qdrant in `/chat`, grounded LLM answer generation, and source
  citations when results exist.
- Optional `/chat` retrieval filtering by document ID.
- Initial chat model provider configuration for OpenAI or disabled mode.
- Character-based context budgeting before LLM generation, with logs for
  retrieved count, context count, context size, truncation, model, top-k, and latency.
- Token usage and configurable cost estimates for generated chat responses.
- CLI evaluation runner for deterministic `/chat` checks plus an optional local
  heuristic semantic judge.
- Deterministic `/agent/respond` workflow evaluation for ticket routes, ticket
  fields, action statuses, and human-approval boundaries.
- Initial LangGraph workflow endpoint that routes between RAG answers and
  ticket classification, persists internal ticket records, and generates
  approval-gated email drafts. Routing is deterministic by default and has an
  opt-in LLM-assisted classifier with deterministic fallback.
- n8n webhook workflow action for ticket notifications. It defaults to
  simulation, records a safe payload summary and explicit network-dispatch
  blockers, and can dispatch a real webhook only when live mode is explicitly
  configured.
- Structured agent workflow audit logs for workflow run IDs, route, action
  names/statuses, ticket IDs, approval flags, router metadata, source counts,
  router latency, and workflow latency without logging user message content or
  email bodies.
- Deterministic services for chunking and initial ticket classification.
- SQLAlchemy model draft for the main domain entities.
- Docker Compose services for PostgreSQL and Qdrant.
- Architecture, API, evaluation, safety, and limitation docs.
- Initial pytest coverage.

Still pending:

- Object storage or durable file retention policy for uploaded documents.
- Persistent workflow audit trail storage.
- Langfuse tracing and richer observability dashboards.
- Live n8n smoke testing with a real webhook URL.
- Deployment setup.

## Tech Stack

- Python 3.12.10
- FastAPI and Pydantic v2
- PostgreSQL, SQLAlchemy 2.x, and Alembic
- Qdrant for vector search
- OpenAI SDK for initial LLM and embedding calls
- LangGraph for agent workflows
- Langfuse for LLM observability
- PyMuPDF for PDF parsing
- Pytest for testing
- Ruff and mypy for code quality
- Docker Compose for local infrastructure

## Local Development

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project with development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Create a local environment file:

```powershell
copy .env.example .env
```

Configure embeddings in `.env`:

```powershell
OPENAI_API_KEY=your_key_here
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

`OPENAI_API_KEY` is the simplest local setup and is used by both embeddings and
chat. Use `EMBEDDING_API_KEY` only if you need a separate key for embeddings.
For future local embeddings, use `EMBEDDING_PROVIDER=local`; the provider is
reserved but not implemented yet, so ingestion will store chunks and skip vector
indexing until a local embedding service is added.

Configure answer generation in `.env`:

```powershell
CHAT_PROVIDER=openai
CHAT_MODEL=gpt-5.4-nano
CHAT_PROMPT_COST_PER_1M_TOKENS=0
CHAT_COMPLETION_COST_PER_1M_TOKENS=0
```

Use `CHAT_API_KEY` only if you need a separate key for chat. Use
`CHAT_PROVIDER=disabled` when you want retrieval and citations without calling an
LLM. Cost estimate rates are intentionally configurable because provider pricing
changes over time; leave both rates at `0` to return token counts without an
estimated dollar cost.

The RAG prompt context is capped before generation:

```powershell
RAG_CONTEXT_MAX_CHARS=6000
```

The current limit is character-based, not token-based.

Configure the n8n webhook boundary in `.env`:

```powershell
N8N_WEBHOOK_MODE=simulated
N8N_WEBHOOK_URL=
N8N_WEBHOOK_TIMEOUT_SECONDS=5
N8N_WEBHOOK_MAX_RETRIES=0
N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=true
```

The default `simulated` mode never sends a network request. To intentionally send
a real n8n webhook from ticket workflows, set:

```powershell
N8N_WEBHOOK_MODE=live
N8N_WEBHOOK_URL=https://your-n8n-host/webhook/your-path
N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=false
```

The webhook URL is never logged. Logs include only whether a URL is configured,
the dispatch mode, timeout/retry settings, dispatch blockers, attempt count,
response status code, and summarized error type. The payload intentionally omits
the original user message and email draft body; it contains only safe ticket
summary fields.

Configure agent routing in `.env`:

```powershell
AGENT_ROUTER_PROVIDER=deterministic
AGENT_ROUTER_MODEL=
```

The default deterministic router keeps local runs cheap and repeatable. To test
LLM-assisted route selection intentionally, set `AGENT_ROUTER_PROVIDER=llm`.
The router uses `CHAT_PROVIDER`, `CHAT_API_KEY` or `OPENAI_API_KEY`, and
`AGENT_ROUTER_MODEL` if set, otherwise `CHAT_MODEL`. Provider/configuration or
invalid-response errors fall back to deterministic routing and are logged only
as metadata.

Use the PowerShell helper for common local workflows:

```powershell
.\scripts\dev.ps1 start
```

`start` runs local infrastructure, migrations, and the API in foreground with
reload. The API is available at `http://localhost:8000`.

You can also run each step separately:

```powershell
.\scripts\dev.ps1 infra
.\scripts\dev.ps1 migrate
.\scripts\dev.ps1 api
```

Check the health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

The `dependencies.n8n` value reports whether n8n dispatch is `simulated`,
`disabled`, fully `live`, or blocked by missing URL or required human approval.
The `dependencies.agent_router` value reports whether agent routing is using
the deterministic default, is ready for `llm`, or is blocked by chat provider/API
key configuration.

Check OpenAI configuration without printing secrets:

```powershell
.\scripts\dev.ps1 auth
```

After adding a valid API key, optionally verify API access without sending
prompts or documents:

```powershell
.\scripts\dev.ps1 auth-live
```

Run the lowest-cost live RAG smoke test against the local API:

```powershell
.\scripts\dev.ps1 smoke
```

The smoke test uploads a tiny `.txt` document, indexes one small embedding batch,
asks one short question with `top_k=1`, and fails if the returned cost estimate
exceeds the configured limit.

Run the controlled live n8n smoke test only when you intentionally want one
external webhook dispatch:

```powershell
.\scripts\dev.ps1 n8n-smoke
```

This command first checks `/health` and refuses to run unless n8n is fully
`live`. It forces `/agent/respond` into ticket mode, so it does not call OpenAI.
After the test, set `N8N_WEBHOOK_MODE=simulated` again for normal local work.

Run the initial deterministic RAG evaluation against the local API:

```powershell
.\scripts\dev.ps1 seed-eval
.\scripts\dev.ps1 eval
```

To add a cheap local answer-correctness signal that tolerates simple paraphrases,
enable the heuristic semantic judge:

```powershell
.\scripts\dev.ps1 eval -SemanticJudge heuristic
```

This is not LLM-as-judge or Ragas. It is a local token-overlap heuristic that is
useful for low-cost regression checks, but it can miss real semantic errors and
can fail valid answers with different wording.

Run the deterministic agent workflow evaluation against the local API:

```powershell
.\scripts\dev.ps1 agent-eval
```

The initial agent dataset lives at `evals/initial_agent_workflow.jsonl`. It is
intentionally limited to ticket workflows so it can validate route selection,
ticket fields, action statuses, email-draft approval, and external-action
boundaries, including the simulated n8n webhook action, without live LLM or
embedding calls. `/agent/respond` answer-mode cases are intentionally kept out
of this default ticket baseline.

Keep `N8N_WEBHOOK_MODE=simulated` when running the default agent eval baseline.
In `live` mode, webhook actions can be marked `completed` after a real external
dispatch, which is intentionally outside the default no-side-effect eval
contract. Also keep `AGENT_ROUTER_PROVIDER=deterministic` unless you
intentionally want the eval run to spend LLM tokens for route selection.

There is also an optional answer-path dataset for disabled-provider runs:

```powershell
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_answer_disabled.jsonl
```

Run it only when the local API is intentionally started without vector search or
with a controlled seeded corpus. It is meant to validate `/agent/respond` answer
contracts without accidentally spending provider tokens.

After seeding the eval corpus, the agent answer path can also be checked against
known source documents:

```powershell
.\scripts\dev.ps1 seed-eval
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_answer_seeded.jsonl -AgentEvalManifestPath reports/evals/eval-corpus-manifest.json
```

This still should be treated as a controlled eval run because it uses the local
RAG configuration behind `/agent/respond`.

There is also an optional LLM-router dataset for ambiguous ticket-like requests:

```powershell
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_router_llm.jsonl
```

Run it only when you intentionally configured `AGENT_ROUTER_PROVIDER=llm`. The
runner checks `/health` first and refuses the dataset unless
`dependencies.agent_router` is `llm`. These cases still keep n8n simulated and
do not require answer-path RAG calls.

The initial dataset lives at `evals/initial_rag.jsonl` and uses the committed
synthetic and public-source corpus under `evals/corpus/`. Public-source snapshots
are generated from the curated FTC URLs in `evals/external_corpus_sources.json`
and include source/license metadata. To refresh those snapshots:

```powershell
.\scripts\dev.ps1 download-corpus
```

The seed script uploads and ingests the corpus documents, then writes a local
manifest under `reports/evals/`, which is ignored by Git. The eval runner uses
that manifest to filter each question to the expected document IDs.

## Validation

Run the main checks before committing:

```powershell
.\scripts\dev.ps1 check
```

## Roadmap

The project follows the phases documented in
[`docs/implementation-plan.md`](docs/implementation-plan.md):

1. Foundation.
2. Persistence with SQLAlchemy and Alembic.
3. Document ingestion and embeddings.
4. RAG.
5. Evaluation.
6. Agent workflows.
7. Observability and deployment.

## Learning Focus

This project is designed for someone with backend experience who wants to learn
AI Engineering through a realistic system. Each phase should make the AI-specific
concepts explicit: chunking, embeddings, vector search, grounded generation,
citations, evaluation, cost, latency, and operational safety.

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/implementation-plan.md`](docs/implementation-plan.md)
- [`docs/api-contracts.md`](docs/api-contracts.md)
- [`docs/evaluation-plan.md`](docs/evaluation-plan.md)
- [`docs/responsible-ai-safety.md`](docs/responsible-ai-safety.md)
- [`docs/known-limitations.md`](docs/known-limitations.md)
