# Evaluation Plan

## Initial Dataset

Create at least 30 question-answer examples from known documents. Each row should
include:

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
