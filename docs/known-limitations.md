# Known Limitations

- Uploaded files are stored on local disk only; there is no object storage,
  retention policy, or cleanup workflow yet.
- `/ingest/{document_id}` parses and chunks documents, but does not yet generate
  embeddings or index vectors in Qdrant.
- `/chat` does not yet call a model or Qdrant.
- Ticket classification is deterministic and keyword-based.
- Evaluation endpoints return placeholder results until a dataset and runner exist.
- Authentication, authorization, rate limits, and file retention are not implemented.
- Public deployment configuration is not complete.
