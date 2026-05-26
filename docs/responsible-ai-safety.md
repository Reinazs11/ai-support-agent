# Responsible AI And Safety

## Principles

- The assistant must answer from retrieved company context whenever the question
  depends on company knowledge.
- If retrieved context is weak or absent, the assistant must say it does not know.
- Sources must reflect actual retrieved chunks, not inferred or guessed references.
- Business actions should be simulated or require human approval until reviewed.
- Email drafts may be generated locally, but sending must remain a separate
  human-approved action.
- Webhook notifications should remain simulated by default. Live outbound
  webhook dispatch is allowed only when the operator explicitly configures live
  mode, a webhook URL, and disables the human-approval blocker for that run.
- Webhook dispatch logs should expose only safe policy metadata, including
  boolean URL presence and explicit dispatch blockers, not the webhook URL or
  request body.
- Webhook URLs or secrets must not be logged. Logs may record whether a URL is
  configured, but not the URL value.

## Data Handling

- Do not log full uploaded documents.
- Do not log API keys, private prompts, credentials, or personally sensitive fields.
- Agent workflow audit logs should include workflow run IDs, route, action
  status, ticket IDs, approval flags, and latency, but not user message content,
  generated answers, retrieved context, or email draft bodies.
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
steps marked as simulated or human-approval-required.
