# Evaluation Plan

## Initial Dataset

The initial committed dataset is `evals/initial_rag.jsonl`. It starts with a
small number of deterministic checks against the live smoke-test document so the
runner can be validated cheaply before expanding to 30 questions.

Each row should include:

- user question;
- expected answer facts;
- expected source document or chunk;
- whether fallback is expected;
- notes about ambiguity or policy constraints.

## Metrics

- Expected information present in answer.
- Correct source retrieved.
- Fallback when context is insufficient.
- Average latency.
- Average cost.
- Error rate.

## Process

1. Run deterministic checks first.
2. Save generated answers and sources.
3. Produce a Markdown report.
4. Track regressions before changing chunking, embeddings, prompts, or retrieval.
5. Add Ragas only after the basic dataset is stable.

Current runner:

```powershell
python -m scripts.run_eval --document-id <document_id_from_smoke_test> --max-total-cost-usd 0.05
```

The runner calls the real `/chat` endpoint, writes JSON and Markdown reports to
`reports/evals/`, and fails by default when deterministic checks do not pass.
