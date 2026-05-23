# Known Limitations

- Uploaded files are stored on local disk only; there is no object storage,
  retention policy, or cleanup workflow yet.
- `/ingest/{document_id}` only generates embeddings and indexes vectors when
  `OPENAI_API_KEY` is configured. Without it, ingestion stores chunks but skips
  vector indexing with an explicit warning.
- `/chat` does not yet call a model or Qdrant.
- Ticket classification is deterministic and keyword-based.
- Evaluation endpoints return placeholder results until a dataset and runner exist.
- Authentication, authorization, rate limits, and file retention are not implemented.
- Public deployment configuration is not complete.
