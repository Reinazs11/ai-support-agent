# AI Support & Knowledge Agent

Production-style AI Engineering portfolio project for a support and
knowledge-base agent.

The system ingests documents, chunks and embeds content, stores vectors in
Qdrant, persists metadata in PostgreSQL, answers questions with grounded RAG,
routes support requests through controlled agent workflows, and evaluates core
behavior with repeatable local datasets.

## Status

The portfolio baseline is functionally complete for local demo/readiness:

- FastAPI backend with explicit HTTP contracts.
- Document upload, parsing, chunking, metadata persistence, and Qdrant indexing.
- OpenAI embeddings and chat generation behind configurable provider services.
- `/chat` RAG answers with citations, fallbacks, latency, token, and cost logs.
- `/agent/respond` workflow with deterministic routing by default, optional
  LLM-router, ticket persistence, email drafts, and n8n notification boundary.
- Deterministic RAG and agent workflow eval runners with Markdown/JSON reports.
- Optional content-minimized Langfuse tracing.
- Docker Compose for local PostgreSQL and Qdrant.
- Deployment readiness and safe local demo documentation.

Not production complete:

- no authentication, authorization, or rate limiting;
- no object storage or retention workflow for uploaded files;
- no platform-specific public deployment guide;
- no production dashboard or queryable audit table.

See [docs/final-checklist.md](docs/final-checklist.md) for the current
completion checklist and remaining gaps.

## Tech Stack

- Python 3.12
- FastAPI and Pydantic
- PostgreSQL, SQLAlchemy, and Alembic
- Qdrant
- OpenAI SDK
- LangGraph
- Langfuse
- Pytest and Ruff
- Docker Compose

## Quickstart

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Create local settings:

```powershell
copy .env.example .env
```

Start infrastructure, run migrations, and start the API:

```powershell
.\scripts\dev.ps1 start
```

If PowerShell blocks scripts, use a per-process bypass:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 start
```

Check readiness:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Safe Defaults

For normal local work and demos:

```powershell
AGENT_ROUTER_PROVIDER=deterministic
N8N_WEBHOOK_MODE=simulated
N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=true
LANGFUSE_ENABLED=false
```

Use `OPENAI_API_KEY` when you want live embeddings or LLM answers. Use
`CHAT_PROVIDER=disabled` and `EMBEDDING_PROVIDER=disabled` when you want to show
controlled fallback contracts without external provider calls.

## Common Commands

```powershell
.\scripts\dev.ps1 check
.\scripts\dev.ps1 auth
.\scripts\dev.ps1 seed-eval
.\scripts\dev.ps1 eval
.\scripts\dev.ps1 agent-eval
```

Optional commands that can call external services:

```powershell
.\scripts\dev.ps1 auth-live
.\scripts\dev.ps1 smoke
.\scripts\dev.ps1 n8n-smoke
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_router_llm.jsonl
```

Run those only when the related live integration is intentionally configured.

## Demo

Use [docs/demo-guide.md](docs/demo-guide.md) for the recommended local demo
path. It shows the safe sequence for RAG, agent workflows, eval reports, and
optional integrations without accidentally enabling live side effects.

## Documentation

- [Architecture](docs/architecture.md)
- [API contracts](docs/api-contracts.md)
- [Evaluation plan](docs/evaluation-plan.md)
- [Responsible AI and safety](docs/responsible-ai-safety.md)
- [Known limitations](docs/known-limitations.md)
- [Deployment readiness](docs/deployment-readiness.md)
- [Demo guide](docs/demo-guide.md)
- [Implementation plan](docs/implementation-plan.md)
- [Final checklist](docs/final-checklist.md)
