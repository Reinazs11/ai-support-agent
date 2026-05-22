# Known Limitations

- The current scaffold does not persist uploaded files.
- `/ingest/{document_id}` does not yet parse, embed, or index documents.
- `/chat` does not yet call a model or Qdrant.
- Ticket classification is deterministic and keyword-based.
- Evaluation endpoints return placeholder results until a dataset and runner exist.
- Authentication, authorization, rate limits, and file retention are not implemented.
- Public deployment configuration is not complete.
- The initial Alembic migration has not yet been exercised against a running
  PostgreSQL container in this branch.
