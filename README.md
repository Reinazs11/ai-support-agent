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

Phase 1, the project foundation, is in place. Phase 2 persistence is merged,
Phase 3 ingestion, indexing, and retrieval are implemented, and Phase 4 RAG
answer generation has started.

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
- Initial CLI evaluation runner for deterministic `/chat` checks.
- Deterministic services for chunking and initial ticket classification.
- SQLAlchemy model draft for the main domain entities.
- Docker Compose services for PostgreSQL and Qdrant.
- Architecture, API, evaluation, safety, and limitation docs.
- Initial pytest coverage.

Still pending:

- Object storage or durable file retention policy for uploaded documents.
- Langfuse tracing and richer observability dashboards.
- LangGraph agent workflow.
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

Run the initial deterministic RAG evaluation against the local API:

```powershell
.\scripts\dev.ps1 seed-eval
.\scripts\dev.ps1 eval
```

The initial dataset lives at `evals/initial_rag.jsonl` and uses the committed
synthetic corpus under `evals/corpus/`. The seed script uploads and ingests those
documents, then writes a local manifest under `reports/evals/`, which is ignored
by Git. The eval runner uses that manifest to filter each question to the
expected document IDs.

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
