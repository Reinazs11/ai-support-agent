# Demo Guide

This guide describes a safe local demo path for the AI Support & Knowledge
Agent. It is designed for portfolio review or a technical interview, where the
goal is to show architecture, behavior, evaluation, and safety boundaries
without relying on uncontrolled external side effects.

## Demo Narrative

Use this project to show:

- document ingestion and chunking;
- OpenAI embeddings and Qdrant vector search when configured;
- grounded RAG answers with citations;
- explicit fallback behavior when context or providers are unavailable;
- deterministic and optional LLM-assisted agent routing;
- ticket workflow orchestration with human-approval boundaries;
- n8n webhook simulation by default;
- evaluation reports for RAG and agent workflows;
- structured logs, token/cost estimates, and optional Langfuse tracing.

The default demo should keep `AGENT_ROUTER_PROVIDER=deterministic` and
`N8N_WEBHOOK_MODE=simulated`. Enable live router, live n8n, or Langfuse only
when the goal of the demo is specifically to show that integration.

## Pre-Demo Checklist

1. Confirm local dependencies are installed:

```powershell
python -m pip install -e ".[dev]"
```

2. Confirm `.env` exists:

```powershell
copy .env.example .env
```

3. Use safe demo defaults:

```powershell
APP_DEBUG=false
AGENT_ROUTER_PROVIDER=deterministic
N8N_WEBHOOK_MODE=simulated
N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=true
LANGFUSE_ENABLED=false
```

4. Configure OpenAI only if the demo includes live embeddings or answers:

```powershell
OPENAI_API_KEY=your_key_here
EMBEDDING_PROVIDER=openai
CHAT_PROVIDER=openai
CHAT_MODEL=gpt-5.4-nano
```

For a no-provider contract demo, set providers to disabled and show controlled
fallbacks instead:

```powershell
EMBEDDING_PROVIDER=disabled
CHAT_PROVIDER=disabled
```

## Start The App

Start infrastructure, run migrations, and start the API:

```powershell
.\scripts\dev.ps1 start
```

If PowerShell blocks script execution, use a per-process bypass:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 start
```

If you prefer separate terminals:

```powershell
.\scripts\dev.ps1 infra
.\scripts\dev.ps1 migrate
.\scripts\dev.ps1 api
```

Check configuration readiness:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Expected safe-demo signals:

- `dependencies.n8n` is `simulated`.
- `dependencies.agent_router` is `deterministic`.
- `dependencies.langfuse` is `disabled` unless tracing is intentionally enabled.
- `dependencies.openai` is `configured` only when a key is present.

## RAG Demo

For the most repeatable RAG demo, seed the committed evaluation corpus:

```powershell
.\scripts\dev.ps1 seed-eval
```

Then run the deterministic RAG evaluation:

```powershell
.\scripts\dev.ps1 eval
```

What this proves:

- uploaded documents are parsed and chunked;
- chunks are persisted;
- embeddings are generated when configured;
- Qdrant retrieval returns expected source material;
- `/chat` answers are grounded in retrieved chunks;
- reports capture pass/fail, latency, sources, and cost estimates.

Optional low-cost semantic heuristic:

```powershell
.\scripts\dev.ps1 eval -SemanticJudge heuristic
```

Use this only as a local regression signal. It is not LLM-as-judge or Ragas.

## Agent Workflow Demo

Run the default no-side-effect agent workflow evaluation:

```powershell
.\scripts\dev.ps1 agent-eval
```

What this proves:

- `/agent/respond` routes ticket-like requests into the workflow;
- ticket classification, save, email draft, and n8n notification actions are
  sequenced;
- external email stays `human_approval_required`;
- n8n stays `simulated`;
- the eval blocks accidental completed external actions.

The default dataset does not require live OpenAI calls because it covers ticket
workflows only.

## Optional LLM-Router Demo

Use this only when explicitly showing the LLM router trade-off:

```powershell
AGENT_ROUTER_PROVIDER=llm
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_router_llm.jsonl
```

The runner checks `/health` first and refuses this dataset unless
`dependencies.agent_router` is `llm`. Keep `N8N_WEBHOOK_MODE=simulated`.

What this proves:

- ambiguous support requests can use a compact LLM route classifier;
- provider/configuration/parse errors fall back to deterministic routing;
- router token usage, latency, and cost can be measured separately.

Current operating decision: deterministic routing remains the default because
the LLM-router dataset is still a small smoke-level check.

## Optional Langfuse Demo

Only enable Langfuse when you intentionally want to show tracing:

```powershell
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

Use `https://us.cloud.langfuse.com` for Langfuse US Cloud. `LANGFUSE_HOST`
remains supported for compatibility, but `LANGFUSE_BASE_URL` is preferred.

Verify credentials and export with a metadata-only smoke trace:

```powershell
.\scripts\dev.ps1 langfuse-smoke
```

Expected trace behavior:

- RAG spans cover answer flow, embedding, vector search, context limiting, and
  generation.
- Agent spans cover workflow execution and router decisions.
- Traces record statuses, counts, model names, token usage, costs, and
  operational IDs.
- Traces must not store prompts, user messages, retrieved chunks, generated
  answers, webhook URLs, or email bodies.

## Optional Live n8n Demo

Do not enable this during the default demo. Use it only when the goal is one
controlled webhook dispatch:

```powershell
N8N_WEBHOOK_MODE=live
N8N_WEBHOOK_URL=https://your-n8n-host/webhook/your-path
N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=false
.\scripts\dev.ps1 n8n-smoke
```

After the run, return to safe defaults:

```powershell
N8N_WEBHOOK_MODE=simulated
N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=true
```

## What To Show In A Review

- `docs/architecture.md` for system structure and trade-offs.
- `docs/evaluation-plan.md` for measurable behavior.
- `docs/responsible-ai-safety.md` for safety boundaries.
- `docs/deployment-readiness.md` for demo deployment constraints.
- Latest JSON/Markdown eval report under `reports/evals/` after local runs.
- `/health` output before running optional live integrations.

## What This Does Not Prove Yet

- Production authentication or authorization.
- Public hosting on a specific platform.
- Object storage or retention policy for uploaded files.
- Deep database/vector-store readiness checks.
- Production-grade LLM-router semantic evaluation.
- LLM-as-judge or Ragas scoring.
- Always-on live n8n integration.
- Queryable audit table or observability dashboard setup.
