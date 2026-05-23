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
- Initial chat model provider configuration for OpenAI or disabled mode.
- Character-based context budgeting before LLM generation, with logs for
  retrieved count, context count, context size, truncation, model, top-k, and latency.
- Placeholder endpoint for evaluation.
- Deterministic services for chunking and initial ticket classification.
- SQLAlchemy model draft for the main domain entities.
- Docker Compose services for PostgreSQL and Qdrant.
- Architecture, API, evaluation, safety, and limitation docs.
- Initial pytest coverage.

Still pending:

- Object storage or durable file retention policy for uploaded documents.
- Metadata-filtered retrieval and token/cost estimates.
- LangGraph agent workflow.
- Langfuse tracing.
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
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=your_key_here
EMBEDDING_MODEL=text-embedding-3-small
```

`OPENAI_API_KEY` is still supported for embeddings when `EMBEDDING_API_KEY` is
empty. For future local embeddings, use `EMBEDDING_PROVIDER=local`; the provider
is reserved but not implemented yet, so ingestion will store chunks and skip
vector indexing until a local embedding service is added.

Configure answer generation in `.env`:

```powershell
CHAT_PROVIDER=openai
CHAT_API_KEY=your_key_here
CHAT_MODEL=gpt-4.1-mini
```

`OPENAI_API_KEY` is also accepted for chat when `CHAT_API_KEY` is empty. Use
`CHAT_PROVIDER=disabled` when you want retrieval and citations without calling
an LLM.

The RAG prompt context is capped before generation:

```powershell
RAG_CONTEXT_MAX_CHARS=6000
```

The current limit is character-based, not token-based. Token and cost estimates
remain planned for a later observability increment.

Start local infrastructure:

```powershell
docker compose up -d postgres qdrant
```

Run the API:

```powershell
python -m uvicorn app.main:app --reload
```

Check the health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Validation

Run the main checks before committing:

```powershell
python -m compileall app scripts tests
python -m pytest
python -m ruff check .
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
