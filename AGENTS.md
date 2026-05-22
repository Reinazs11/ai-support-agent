# AGENTS.md

## Project Goal

Build a production-style AI Support & Knowledge Agent as an AI Engineering
portfolio project.

The project should evolve in small, testable, well-scoped increments. The main
goal is not to generate as much code as possible, but to build a system that is
understandable, maintainable, measurable, and explainable in a technical
interview.

The final system should eventually support:

- document ingestion;
- parsing and chunking;
- embeddings;
- vector storage in Qdrant;
- metadata storage in PostgreSQL;
- RAG-based question answering;
- answers with real sources and citations;
- ticket or lead classification;
- controlled agentic workflows;
- automated evaluation;
- structured logs, latency tracking, cost tracking, and tracing;
- local execution with Docker Compose;
- public deployment and demo documentation.

Treat this as a real backend project, even though it is also a study project.

Follow `docs/implementation-plan.md` in order. Update it when behavior,
architecture, setup, or scope changes.

---

## Core Engineering Principles

- Prefer simple, explicit, maintainable code over clever abstractions.
- Build in small, reviewable increments.
- Keep each task narrow and scoped.
- Avoid unrelated refactors during feature work.
- Do not implement multiple roadmap stages in one task unless explicitly requested.
- Keep public API contracts stable unless a change is clearly justified.
- Cover important behavior with tests.
- Do not hide incomplete behavior behind production-looking APIs.
- Make trade-offs explicit when choosing an approach.
- Prefer readable code that a junior-to-mid backend developer could maintain.

---

## Technology Stack

The agent may choose the most appropriate tools, libraries, frameworks, and
services for each task, but choices must be conservative, well-justified, and
aligned with the project goals.

Do not introduce or replace frameworks, libraries, databases, hosted services, or
architectural patterns without first explaining:

- why the dependency is needed;
- what problem it solves;
- why the existing stack is not enough;
- what trade-offs it introduces.

Do not add technologies only because they are popular, new, or interesting.

Do not introduce experimental, obscure, poorly maintained, or unnecessary
dependencies.

---

## Environment And Tooling Rules

This project is developed on Windows, so prefer commands that work well in
PowerShell.

Use `python -m ...` commands when possible because they are more reliable across
virtual environments.

When applicable, run:

```powershell
python -m compileall app scripts tests
python -m pytest
python -m ruff check .
```

Do not install global system tools, change OS settings, or modify machine-level
configuration unless explicitly requested.

If a required tool is missing, report it clearly and recommend the exact next
step instead of silently skipping validation.

Do not assume that Git, GitHub CLI, Docker, pytest, Ruff, mypy, or other tools are
available until verified.

---

## Placeholder And Mock Policy

Placeholders are allowed only when they make the architecture clearer or unblock
the next small step.

Every placeholder must be obvious.

Good example:

```python
class PlaceholderEmbeddingService:
    """Temporary implementation until real embeddings are added."""
```

Bad example:

```python
class EmbeddingService:
    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]
```

Do not make fake implementations look production-ready.

When finishing a task, update documentation when needed and clearly report:

- what is fully functional;
- what is partial;
- what is mocked;
- what is placeholder;
- what still needs to be implemented.

---

## Agentic Development Workflow

For non-trivial tasks, first provide a short plan before editing code.

The plan should include:

1. what will be changed;
2. which files are likely to be touched;
3. what is explicitly out of scope;
4. risks or assumptions.

During implementation:

- keep the diff small;
- avoid unrelated refactors;
- avoid broad rewrites;
- preserve existing contracts unless a change is approved;
- add or update tests with the behavior;
- update documentation only when behavior, architecture, or setup changes.

After implementation, perform a self-review before finalizing.

---

## Testing Rules

Use pytest.

Do not remove tests just to make the suite pass.

Do not weaken assertions without explaining why.

For new functionality, test both success and failure cases when practical.

If a test requires an external service, make that requirement explicit.

---

## Documentation Rules

Keep documentation short, accurate, and current.

Update documentation when behavior, architecture, setup, or API contracts change.

Important documentation files may include:

- `README.md`
- `docs/architecture.md`
- `docs/implementation-plan.md`
- `docs/api-contracts.md`
- `docs/evaluation-plan.md`
- `docs/responsible-ai-safety.md`
- `docs/known-limitations.md`

Do not over-document obvious code.

Document decisions, trade-offs, limitations, and validation steps.

---

## Security And Privacy Rules

Never commit:

- API keys;
- tokens;
- passwords;
- private credentials;
- `.env` files;
- raw private documents;
- production data.

Never log:

- API keys;
- tokens;
- passwords;
- authentication headers;
- full prompts containing sensitive content;
- complete uploaded documents;
- raw retrieved context when it may contain private information.

Prefer logs with:

- request IDs;
- document IDs;
- chunk IDs;
- counts;
- statuses;
- durations;
- summarized error types.

---

## Database And Migration Rules

When database models change, explain whether a migration is needed.

Do not reset, delete, or overwrite local databases without explicit approval.

Do not use destructive commands automatically.

Keep SQLAlchemy models, database setup, and API schemas separate.

Prefer clear model names and explicit relationships.

---

## Final Response Format After Each Task

After completing a task, respond with:

1. files changed;
2. behavior implemented;
3. tests added or updated;
4. validation commands run;
5. what is still partial, mocked, or placeholder;
6. risks or limitations;
7. recommended next step.

Be honest about failures, missing tools, skipped commands, and incomplete work.

Do not present partial work as complete.
