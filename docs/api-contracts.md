# API Contracts

Base prefix: `/api/v1`. During local development the same routes are also exposed
without the prefix for convenience.

## GET /health

Returns service status and dependency configuration state.

## POST /documents

Accepts multipart upload under field `file`.

Response:

```json
{
  "document_id": "uuid",
  "filename": "handbook.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "status": "registered",
  "next_step": "POST /ingest/{document_id}"
}
```

## POST /ingest/{document_id}

Parses the stored document, chunks its text, and persists chunk metadata in
PostgreSQL. When the configured embedding provider is available, it also
generates embeddings and indexes chunk vectors in Qdrant.

Response:

```json
{
  "document_id": "uuid",
  "status": "ingested",
  "chunks_indexed": 3,
  "vectors_indexed": 0,
  "warnings": [
    "Embedding and Qdrant indexing were skipped because the configured embedding provider is unavailable or not configured."
  ]
}
```

## POST /chat

Request:

```json
{
  "question": "What is the refund policy?",
  "top_k": 5,
  "document_ids": ["document-uuid"]
}
```

`document_ids` is optional. When provided, retrieval is limited to chunks whose
Qdrant payload has one of those document IDs.

Response includes `answer`, `sources`, `confidence`, `retrieval_status`, and
`usage`.

Example usage payload:

```json
{
  "prompt_tokens": 1000,
  "completion_tokens": 200,
  "total_tokens": 1200,
  "estimated_cost_usd": 0.0008
}
```

`usage` is `null` when the chat model provider does not return token usage, or
when generation is not called. `estimated_cost_usd` is `null` unless
`CHAT_PROMPT_COST_PER_1M_TOKENS` or `CHAT_COMPLETION_COST_PER_1M_TOKENS` is
configured.

Current retrieval statuses include:

- `not_configured`: embedding provider or vector store is unavailable.
- `embedding_unavailable`: the question could not be embedded.
- `no_results`: Qdrant returned no relevant chunks.
- `insufficient_context`: chunks were retrieved, but the model determined that
  they do not contain enough information.
- `generation_not_configured`: Qdrant returned chunks, but no chat model
  provider is configured.
- `generation_failed`: Qdrant returned chunks, but the configured chat model
  provider failed.
- `generated`: Qdrant returned chunks and the chat model generated an answer.

Generated answers are prompted only with the chunks returned by retrieval. When
no chunks are available, the answer uses the explicit fallback:
`I do not have enough information to answer safely.`

Before calling the chat model, the service applies `RAG_CONTEXT_MAX_CHARS` to
the retrieved chunk text. Sources in the response reflect chunks included in the
bounded context, not every raw vector-search result.

## POST /tickets/classify

Request:

```json
{
  "subject": "API is down",
  "body": "Customer reports a critical production issue",
  "customer_tier": "enterprise"
}
```

Response includes category, priority, escalation flag, and rationale.

## POST /agent/respond

Runs the Phase 6 workflow layer. The endpoint can route to a grounded RAG answer
or to deterministic ticket classification. Ticket workflows persist an internal
ticket record and generate a local email draft. Email sending remains
human-approval-required. n8n webhook notification defaults to simulation, but it
can perform a real outbound POST when live mode is explicitly configured.

The n8n boundary exposes configuration for mode, URL presence, timeout, retries,
human-approval requirement, and network-dispatch blockers in structured logs.
Supported modes are `simulated`, `disabled`, and `live`. Live mode only
dispatches when a webhook URL is configured and
`N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL=false`. Webhook URLs, request bodies,
response bodies, user messages, and email draft bodies are not logged.

Request:

```json
{
  "message": "The production API is down and this is critical.",
  "mode": "auto",
  "top_k": 5,
  "document_ids": ["document-uuid"],
  "customer_tier": "enterprise"
}
```

`mode` can be:

- `auto`: use a simple deterministic router.
- `answer`: force the RAG answer path.
- `ticket`: force the ticket classification path.

Response:

```json
{
  "route": "human_escalation",
  "answer": null,
  "confidence": null,
  "retrieval_status": null,
  "sources": [],
  "usage": null,
  "ticket": {
    "id": "ticket-uuid",
    "status": "open",
    "category": "technical_support",
    "priority": "high",
    "should_escalate": true,
    "rationale": "Initial deterministic classifier; replace with evaluated LLM flow later."
  },
  "email_draft": {
    "subject": "Re: The production API is down and this is critical.",
    "body": "Hi,\n\nThanks for contacting support. ...",
    "requires_approval": true
  },
  "actions": [
    {
      "name": "classify_ticket",
      "status": "simulated",
      "reason": "Ticket classification uses the deterministic local classifier."
    },
    {
      "name": "save_ticket",
      "status": "completed",
      "reason": "Ticket persisted to local metadata storage."
    },
    {
      "name": "draft_email",
      "status": "completed",
      "reason": "Email draft generated locally from ticket context."
    },
    {
      "name": "send_email",
      "status": "human_approval_required",
      "reason": "Workflow does not send external communications automatically."
    },
    {
      "name": "notify_n8n_webhook",
      "status": "simulated",
      "reason": "n8n webhook notification simulated locally; no external request was sent."
    },
    {
      "name": "request_human_review",
      "status": "human_approval_required",
      "reason": "High-priority ticket workflow requires human review."
    }
  ],
  "human_approval_required": true
}
```

In live mode, `notify_n8n_webhook` can return:

- `completed`: a POST to the configured n8n webhook returned a 2xx status.
- `failed`: the webhook returned a non-2xx status or all retry attempts failed.
- `human_approval_required`: live dispatch was blocked because human approval is
  still required.

## POST /evals/run

Placeholder endpoint for future API-triggered evaluation runs. Use
`python -m scripts.run_eval` for the current controlled local evaluation flow.
This endpoint should be protected or disabled before public deployment.
