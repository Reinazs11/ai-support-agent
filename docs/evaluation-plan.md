# Evaluation Plan

## Initial Dataset

The initial committed dataset is `evals/initial_rag.jsonl`. It currently has 30
deterministic checks against the synthetic and FTC public-source files in
`evals/corpus/` so the runner can be validated cheaply before adding richer
answer-quality evaluation.

The corpus also includes FTC public-source snapshots generated from
`evals/external_corpus_sources.json`. Refresh them with:

```powershell
python -m scripts.download_eval_corpus
```

Downloaded corpus files must keep source URL and license metadata in the file
header so answers can be traced back to real source material.

Each row should include:

- user question;
- expected answer facts;
- expected source document or chunk;
- whether fallback is expected;
- notes about ambiguity or policy constraints.

For deterministic answer checks, use `expected_answer_contains` when a fact must
appear exactly as written. Use `expected_answer_contains_any` for equivalent
English variants of the same fact. Each variant group passes when at least one
value in that group appears in the answer. RAG answers and deterministic eval
expectations are English-only so failures point to answer quality instead of
language drift.

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
.\scripts\dev.ps1 seed-eval
.\scripts\dev.ps1 eval
```

The seed script uploads and ingests the eval corpus through the local API, then
writes a local manifest with the generated document IDs. The runner calls the
real `/chat` endpoint, uses the manifest to filter each case to the expected
source documents, writes JSON and Markdown reports to `reports/evals/`, and
fails by default when deterministic checks do not pass. If the API is not
running, it exits with a short connection message instead of a stack trace.
Failed cases include failure reasons plus expected and actual status, answer
checks, and source titles in the generated reports.
