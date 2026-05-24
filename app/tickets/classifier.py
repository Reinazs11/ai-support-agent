from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    category: str
    priority: str
    should_escalate: bool
    rationale: str


HIGH_PRIORITY_TERMS = {"urgent", "down", "critical"}
BILLING_TERMS = {"invoice", "billing", "payment"}
TECHNICAL_TERMS = {"error", "bug", "failure", "api", "login", "password"}


def classify_ticket_text(text: str) -> Classification:
    normalized = text.lower()
    priority = "high" if any(term in normalized for term in HIGH_PRIORITY_TERMS) else "normal"
    should_escalate = priority == "high"

    if any(term in normalized for term in BILLING_TERMS):
        category = "billing"
    elif any(term in normalized for term in TECHNICAL_TERMS):
        category = "technical_support"
    else:
        category = "general_support"

    return Classification(
        category=category,
        priority=priority,
        should_escalate=should_escalate,
        rationale="Initial deterministic classifier; replace with evaluated LLM flow later.",
    )
