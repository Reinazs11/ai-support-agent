# Deployment Readiness

This project is deployment-ready as a portfolio demo backend, not as a complete
production service. The deployment target should run the API container, a
PostgreSQL database, and a Qdrant instance. External LLM, Langfuse, and n8n
integrations are optional and must be explicitly configured.

## Required Runtime Services

- API container built from `docker/Dockerfile`.
- PostgreSQL reachable through `DATABASE_URL`.
- Qdrant reachable through `QDRANT_URL`.
- Persistent storage for uploaded files if document upload is enabled beyond a
  short-lived demo.

The Docker image includes the application package, `alembic.ini`, and
`migrations/` so migrations can be run from the image before starting the API.
The local `docker-compose.yml` is still a development compose file because it
mounts the repository into the API container.

When the API runs inside Docker Compose, use service hostnames:

- `DATABASE_URL=postgresql+psycopg://support_agent:support_agent@postgres:5432/support_agent`
- `QDRANT_URL=http://qdrant:6333`

When the API runs directly on the host machine against Compose-managed
infrastructure, use localhost:

- `DATABASE_URL=postgresql+psycopg://support_agent:support_agent@localhost:5432/support_agent`
- `QDRANT_URL=http://localhost:6333`

## Environment Groups

Core:

- `APP_ENV`
- `APP_DEBUG`
- `DATABASE_URL`
- `QDRANT_URL`
- `QDRANT_COLLECTION`
- `UPLOAD_DIR`
- `RAG_CONTEXT_MAX_CHARS`
- `RAG_CONTEXT_MAX_TOKENS`

OpenAI:

- `OPENAI_API_KEY`, or provider-specific `EMBEDDING_API_KEY` and `CHAT_API_KEY`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `CHAT_PROVIDER`
- `CHAT_MODEL`
- `CHAT_PROMPT_COST_PER_1M_TOKENS`
- `CHAT_COMPLETION_COST_PER_1M_TOKENS`
- `PROVIDER_MAX_RETRIES`
- `PROVIDER_RETRY_INITIAL_WAIT_SECONDS`
- `PROVIDER_RETRY_MAX_WAIT_SECONDS`

Agent workflow:

- `AGENT_ROUTER_PROVIDER`
- `AGENT_ROUTER_MODEL`
- `N8N_WEBHOOK_MODE`
- `N8N_WEBHOOK_URL`
- `N8N_WEBHOOK_TIMEOUT_SECONDS`
- `N8N_WEBHOOK_MAX_RETRIES`
- `N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL`

Observability:

- `LANGFUSE_ENABLED`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL`
- `LANGFUSE_HOST`

## Startup Order

1. Start PostgreSQL and Qdrant.
2. Run migrations:

```powershell
python -m alembic upgrade head
```

3. Start the API:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. Check readiness:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

`/health` currently reports configuration readiness, not deep connectivity
checks. It shows OpenAI key presence, n8n dispatch state, agent-router state,
and Langfuse tracing state. A future deployment hardening step should add real
database/vector-store connectivity checks or a separate readiness endpoint.

## Safe Demo Defaults

For a public demo, prefer:

- `APP_DEBUG=false`
- `AGENT_ROUTER_PROVIDER=deterministic`
- `N8N_WEBHOOK_MODE=simulated`
- `N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=true`
- `LANGFUSE_ENABLED=false` unless Langfuse credentials are intentionally
  configured
- conservative upload limits through `MAX_UPLOAD_MB`

Only enable live n8n dispatch when the webhook URL is correct and the run is
specifically testing external side effects.

## Not Yet Production Complete

- No authentication or authorization.
- No rate limiting.
- No object storage, retention policy, or cleanup job for uploaded files.
- No deep readiness checks for PostgreSQL or Qdrant.
- No queryable audit table.
- No deployment-specific secret manager integration.
- No public hosting guide for a specific platform.
