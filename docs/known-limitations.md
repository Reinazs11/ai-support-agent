# Known Limitations

- Uploaded files are stored on local disk only; there is no object storage,
  retention policy, or cleanup workflow yet.
- `/ingest/{document_id}` only generates embeddings and indexes vectors when
  the configured embedding provider is available. OpenAI works through
  `EMBEDDING_API_KEY` or the backward-compatible `OPENAI_API_KEY`; local
  embeddings are prepared in configuration but not implemented yet.
- `/chat` retrieves from Qdrant and can call an OpenAI chat model when
  configured. Current metadata filtering is limited to document IDs, context
  budgeting is character-based rather than token-aware, and cost estimates
  require configured per-token rates.
- Ticket classification is deterministic and keyword-based.
- The CLI evaluation runner supports deterministic RAG evals plus an optional
  local heuristic semantic judge. The heuristic is not LLM-as-judge or Ragas: it
  scores normalized token overlap, so it can miss contradictions or reject valid
  answers with different wording. `/evals/run` still returns placeholder results
  and the committed dataset is intentionally small.
- Agent workflows are starting in Phase 6. The workflow endpoint can route to
  RAG answers or deterministic ticket classification and persists internal
  ticket records. Email drafts are deterministic local drafts and are never sent
  automatically. n8n webhook notifications default to simulated mode, but live
  mode can POST to a configured webhook URL when human approval is explicitly
  disabled. n8n mode, URL presence, timeout, retries, approval policy, and
  explicit network-dispatch blockers are logged without exposing the webhook
  URL, user message, or email body. LLM-assisted routing is not implemented yet.
  External business actions remain simulated or human-approved by default.
- The evaluation suite has an initial deterministic `/agent/respond` workflow
  eval for ticket routes, action sequencing, email-draft approval, and workflow
  side-effect boundaries. It also has an optional disabled-provider answer-path
  dataset and a small seeded-corpus answer-path dataset for `/agent/respond`.
  These optional datasets still depend on the local API/provider configuration
  used during the run. The suite covers n8n live dispatch with fake HTTP clients,
  but does not yet include a live n8n integration test, persistent audit trail
  storage, or LLM-assisted routing.
- Agent workflow audit logs are structured and content-minimized, but they are
  emitted as application logs only. There is no queryable audit table or trace
  dashboard yet.
- Authentication, authorization, rate limits, and file retention are not implemented.
- Public deployment configuration is not complete.
