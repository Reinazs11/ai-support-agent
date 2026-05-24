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

## POST /evals/run

Placeholder endpoint for future API-triggered evaluation runs. Use
`python -m scripts.run_eval` for the current controlled local evaluation flow.
This endpoint should be protected or disabled before public deployment.
