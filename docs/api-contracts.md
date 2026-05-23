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
PostgreSQL. Embedding generation and Qdrant indexing are still pending.

Response:

```json
{
  "document_id": "uuid",
  "status": "ingested",
  "chunks_indexed": 3,
  "warnings": []
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
