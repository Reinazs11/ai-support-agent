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
  "top_k": 5
}
```

Response includes `answer`, `sources`, `confidence`, and `retrieval_status`.
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
`Nao encontrei informacao suficiente para responder com seguranca.`

## POST /tickets/classify

Request:

```json
{
  "subject": "API fora do ar",
  "body": "Cliente relata problema urgente",
  "customer_tier": "enterprise"
}
```

Response includes category, priority, escalation flag, and rationale.

## POST /evals/run

Runs an evaluation dataset in controlled/local mode. This endpoint should be
protected or disabled before public deployment.
