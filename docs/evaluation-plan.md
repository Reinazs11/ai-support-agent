# Evaluation Plan

## Initial Dataset

The initial committed dataset is `evals/initial_rag.jsonl`. It currently has 30
checks against the synthetic and FTC public-source files in `evals/corpus/` so
the runner can be validated cheaply before adding optional LLM-as-judge or
Ragas-style evaluation later.

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
- optional forbidden answer terms;
- optional answer length limits;
- notes about ambiguity or policy constraints.

For deterministic answer checks, use `expected_answer_contains` when a fact must
appear exactly as written. Use `expected_answer_contains_any` for equivalent
English variants of the same fact. Each variant group passes when at least one
value in that group appears in the answer. RAG answers and deterministic eval
expectations are English-only so failures point to answer quality instead of
language drift. The runner normalizes deterministic answer matching for case,
diacritics, punctuation, apostrophes, hyphens, and repeated whitespace before
checking substrings, while reports still preserve the original generated answer.
In addition to exact facts and sources, each case receives a deterministic
answer-quality check. The quality check verifies that answers are present,
fallback responses use the canonical fallback when expected, generated answers
do not use the fallback, optional forbidden terms are absent, and optional
answer length limits are respected.

The runner can also enable a local semantic heuristic judge with
`--semantic-judge heuristic`. This judge does not call an external provider. It
scores expected answer fact groups by normalized token overlap against the
generated answer and reports semantic pass/fail, score, threshold, rationale,
and failure reasons. When enabled and applicable to a generated-answer case,
semantic pass/fail becomes the answer-correctness gate, while the deterministic
substring answer check remains visible in reports for debugging. Retrieval
status, source titles, fallback behavior, forbidden terms, and length limits
remain deterministic contract checks because they are objective and cheaper to
debug.

This heuristic judge is intentionally not described as robust semantic
evaluation. It does not understand entailment, contradictions, partial credit
beyond token overlap, or whether an answer is faithful to the retrieved source.
It is useful as a free regression signal before workflow behavior changes, but
LLM-as-judge or Ragas-style evaluation is still needed later if the project
needs stronger answer-quality grading.

## Metrics

- Expected information present in answer.
- Correct source retrieved.
- Fallback when context is insufficient.
- Deterministic answer quality score.
- Optional semantic answer score.
- Average latency.
- Average cost.
- Error rate.

## Process

1. Run deterministic checks first.
2. Save generated answers and sources.
3. Produce a Markdown report.
4. Track regressions before changing chunking, embeddings, prompts, or retrieval.
5. Enable the local semantic heuristic when answer phrasing needs a softer
   low-cost correctness signal.
6. Add LLM-as-judge or Ragas after Phase 6 workflows are stable enough that the
   evaluation targets will not immediately change.

Current runner:

```powershell
.\scripts\dev.ps1 seed-eval
.\scripts\dev.ps1 eval
.\scripts\dev.ps1 eval -SemanticJudge heuristic
```

The seed script uploads and ingests the eval corpus through the local API, then
writes a local manifest with the generated document IDs. The runner calls the
real `/chat` endpoint, uses the manifest to filter each case to the expected
source documents, writes JSON and Markdown reports to `reports/evals/`, and
fails by default when deterministic checks do not pass. If the API is not
running, it exits with a short connection message instead of a stack trace.
Failed cases include failure reasons plus expected and actual status, answer
checks, quality checks, semantic judge details, and source titles in the
generated reports.
