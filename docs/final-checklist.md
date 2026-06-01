# Final Checklist

This checklist summarizes the current project state for portfolio review.

## Complete For Local Demo

- FastAPI backend with stable local contracts.
- PostgreSQL metadata persistence with Alembic migrations.
- Document upload, parsing, chunking, and local file storage.
- OpenAI embedding provider and Qdrant indexing.
- Grounded RAG answer generation with citations.
- Explicit RAG fallback statuses.
- Token usage and configurable cost estimates.
- Deterministic RAG evaluation with reports.
- Optional local heuristic semantic judge.
- LangGraph agent workflow for answer or ticket routes.
- Ticket persistence and local email draft generation.
- Human-approval boundary for external communication.
- n8n webhook action with simulated default and guarded live smoke helper.
- Optional LLM-assisted router with deterministic fallback.
- Agent workflow evaluation datasets and reports.
- Content-minimized structured logs.
- Optional content-minimized Langfuse tracing.
- Deployment readiness documentation.
- Safe local demo guide.

## Recommended Final Validation

Run local static/test checks:

```powershell
.\scripts\dev.ps1 check
```

For a full local RAG demo with providers configured:

```powershell
.\scripts\dev.ps1 seed-eval
.\scripts\dev.ps1 eval
```

For the default no-side-effect agent workflow demo:

```powershell
.\scripts\dev.ps1 agent-eval
```

Optional, only when intentionally configured:

```powershell
.\scripts\dev.ps1 smoke
.\scripts\dev.ps1 langfuse-smoke
.\scripts\dev.ps1 n8n-smoke
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_router_llm.jsonl
```

## Demo Positioning

Present this as a production-style portfolio backend, not a production-hosted
SaaS service. The strongest points are:

- grounded RAG with citations;
- controlled fallbacks;
- measured evals;
- explicit cost and latency reporting;
- human-approved workflow boundaries;
- safe integration defaults;
- honest documentation of limitations.

## Not Production Complete

- Authentication and authorization.
- Rate limiting.
- Object storage for uploaded files.
- Retention and cleanup policies.
- Platform-specific public deployment.
- Secret manager integration.
- Deep readiness checks for PostgreSQL and Qdrant.
- Queryable audit table.
- Observability dashboards and sampling policy.
- Broader LLM-router benchmark.
- LLM-as-judge or Ragas evaluation.

## Sensible Next Enhancements

1. Run a controlled Langfuse smoke with real credentials and document the result.
2. Choose one hosting target and write a platform-specific deployment guide.
3. Add basic auth or API-key protection before any public deployment.
4. Add object storage and file cleanup if uploads will persist beyond demos.
