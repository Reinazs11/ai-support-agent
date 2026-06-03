# Evaluation Plan

## Initial Dataset

The initial committed dataset is `evals/initial_rag.jsonl`. It currently has 33
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
- optional `metadata_filter` values passed through to `/chat`;
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
- Agent workflow route correctness.
- Agent workflow action correctness and approval boundaries.
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
6. Keep the deterministic agent workflow evaluation baseline green before
   relying on LLM-assisted routing or additional external integrations.
7. Add LLM-as-judge or Ragas after Phase 6 workflows are stable enough that the
   evaluation targets will not immediately change.

## Agent Workflow Evaluation

The initial agent workflow evaluation targets `/agent/respond`, not just
`/chat`. It is deterministic and uses `evals/initial_agent_workflow.jsonl`.
Each case asserts:

- expected route: `classify_ticket` or `human_escalation`;
- expected ticket category and priority when a ticket is created;
- expected action names and statuses, especially `human_approval_required`;
- whether an email draft is expected;
- that no external send/webhook action is marked completed automatically.

The default baseline runs without live LLM or embedding calls because
`evals/initial_agent_workflow.jsonl` contains ticket workflows only. The
optional `evals/agent_answer_disabled.jsonl` dataset covers `mode=answer`
disabled-provider behavior and checks route, fallback answer text,
`retrieval_status`, source count, and absence of workflow actions. Run it only
when the local API is intentionally started without vector search or with a
controlled seeded corpus, so it does not accidentally spend provider tokens.
`evals/agent_answer_seeded.jsonl` covers a small seeded-corpus answer path and
uses the eval corpus manifest to filter each case to its expected source
documents. It should run after `seed-eval`, with the same caution as RAG evals:
the local API configuration determines whether providers are called.
The default ticket dataset assumes `N8N_WEBHOOK_MODE=simulated`. In that mode,
the n8n webhook action must stay `simulated`, not `completed`. The agent eval
runner checks `/health` and refuses datasets that expect simulated n8n when the
API reports `n8n=live`; use `n8n-smoke` for controlled live webhook dispatch.
Keep
`AGENT_ROUTER_PROVIDER=deterministic` for the default baseline unless the goal
is an explicit LLM-routing eval run.

LLM-assisted agent routing is currently opt-in and is not part of the default
agent eval baseline. Before using it in a demo or making it the default, add
ambiguous auto-mode routing cases and compare deterministic vs. LLM router
behavior with explicit cost and latency reporting.
The optional `evals/agent_router_llm.jsonl` dataset contains ambiguous
ticket-like auto-mode requests that require `AGENT_ROUTER_PROVIDER=llm`. The
runner checks `/health` and refuses this dataset unless
`dependencies.agent_router` is `llm`, preventing accidental execution against
the deterministic default. The current LLM-router dataset intentionally avoids
answer-path RAG cases so the first router eval spends only route-classification
tokens and keeps n8n simulated. Agent eval reports include aggregated router
prompt tokens, completion tokens, total tokens, and estimated router cost when
the API response includes router usage.

Latest controlled LLM-router measurement:

- Date: May 31, 2026.
- Dataset: `evals/agent_router_llm.jsonl`.
- Environment guard: `/health` reported `agent_router=llm`, OpenAI configured,
  and n8n simulated.
- Result: 3 evaluated, 3 passed, 0 failed.
- Average latency: 2223.24 ms.
- Router usage: 332 prompt tokens, 105 completion tokens, 437 total tokens.
- Estimated router cost: 0.00019765 USD with the configured token rates.

Operational decision: keep deterministic routing as the default and use
LLM-assisted routing only when explicitly measuring or demonstrating ambiguous
auto-mode support requests. The current LLM-router eval is a useful smoke-level
signal, not a production-quality semantic routing benchmark. Before making LLM
routing the default, expand the dataset with answer-vs-ticket contrast cases,
negative ticket cases, and repeated runs to observe provider latency and
fallback frequency.

For a single controlled live n8n check, use:

```powershell
.\scripts\dev.ps1 n8n-smoke
```

The command checks `/health` first and refuses to run unless n8n is fully
`live`. It sends one ticket-mode `/agent/respond` request and expects
`notify_n8n_webhook` to complete.

Current runner:

```powershell
.\scripts\dev.ps1 seed-eval
.\scripts\dev.ps1 eval
.\scripts\dev.ps1 eval -SemanticJudge heuristic
.\scripts\dev.ps1 agent-eval
.\scripts\dev.ps1 n8n-smoke
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_answer_disabled.jsonl
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_answer_seeded.jsonl -AgentEvalManifestPath reports/evals/eval-corpus-manifest.json
.\scripts\dev.ps1 agent-eval -AgentEvalDatasetPath evals/agent_router_llm.jsonl
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

The agent eval runner calls `/agent/respond`, writes JSON and Markdown reports
to `reports/evals/`, and fails by default when a route, ticket field, action
status, human-approval flag, email-draft expectation, answer fallback contract,
retrieval status, source count, source titles, or forbidden completed action
does not match the dataset. When `--document-manifest-path` is provided, source
titles in the dataset are resolved to document IDs before the request is sent.
The runner also records router provider/model metadata and aggregates router
usage/cost when available.
