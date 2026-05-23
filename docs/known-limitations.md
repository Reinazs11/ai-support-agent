# Known Limitations

- Uploaded files are stored on local disk only; there is no object storage,
  retention policy, or cleanup workflow yet.
- `/ingest/{document_id}` only generates embeddings and indexes vectors when
  the configured embedding provider is available. OpenAI works through
  `EMBEDDING_API_KEY` or the backward-compatible `OPENAI_API_KEY`; local
  embeddings are prepared in configuration but not implemented yet.
- `/chat` does not yet call a model or Qdrant.
- Ticket classification is deterministic and keyword-based.
- Evaluation endpoints return placeholder results until a dataset and runner exist.
- Authentication, authorization, rate limits, and file retention are not implemented.
- Public deployment configuration is not complete.
