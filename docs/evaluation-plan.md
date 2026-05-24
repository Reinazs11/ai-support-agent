# Evaluation Plan

## Initial Dataset

The initial committed dataset is `evals/initial_rag.jsonl`. It starts with a
small number of deterministic checks against the synthetic files in
`evals/corpus/` so the runner can be validated cheaply before expanding to 30
questions.

Each row should include:

- user question;
- expected answer facts;
- expected source document or chunk;
- whether fallback is expected;
- notes about ambiguity or policy constraints.

For deterministic answer checks, use `expected_answer_contains` when a fact must
appear exactly as written. Use `expected_answer_contains_any` for equivalent
variants, for example English and Portuguese wording of the same fact. Each
variant group passes when at least one value in that group appears in the answer.

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
python -m scripts.seed_eval_corpus
python -m scripts.run_eval --document-manifest-path reports/evals/eval-corpus-manifest.json --max-total-cost-usd 0.05
```

The seed script uploads and ingests the eval corpus through the local API, then
writes a local manifest with the generated document IDs. The runner calls the
real `/chat` endpoint, uses the manifest to filter each case to the expected
source documents, writes JSON and Markdown reports to `reports/evals/`, and
fails by default when deterministic checks do not pass. If the API is not
running, it exits with a short connection message instead of a stack trace.
