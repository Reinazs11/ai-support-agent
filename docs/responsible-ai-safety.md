# Responsible AI And Safety

## Principles

- The assistant must answer from retrieved company context whenever the question
  depends on company knowledge.
- If retrieved context is weak or absent, the assistant must say it does not know.
- Sources must reflect actual retrieved chunks, not inferred or guessed references.
- Business actions should be simulated or require human approval until reviewed.
- Email drafts may be generated locally, but sending must remain a separate
  human-approved action.

## Data Handling

- Do not log full uploaded documents.
- Do not log API keys, private prompts, credentials, or personally sensitive fields.
- Keep retention and deletion behavior explicit before using real company data.

## Human-In-The-Loop

Escalate when:

- the ticket is high priority;
- the user requests a sensitive action;
- the model confidence is low;
- the workflow would send external communication.

## Workflow Evaluation

Before connecting external workflow tools, evaluate that agent workflows choose
the expected route, create the expected internal actions, and keep send/webhook
steps marked as human-approval-required.
