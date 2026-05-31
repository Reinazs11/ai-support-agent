from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    user_message: str
    workflow_run_id: str
    mode: Literal["auto", "answer", "ticket"]
    top_k: int | None
    document_ids: list[str]
    customer_tier: str | None
    route: Literal["answer", "classify_ticket", "save_ticket", "draft_email", "human_escalation"]
    answer: str
    confidence: str
    retrieval_status: str
    sources: list[Any]
    usage: Any
    ticket_category: str
    ticket_priority: str
    ticket_should_escalate: bool
    ticket_rationale: str
    ticket_subject: str
    ticket_body: str
    ticket_id: str
    ticket_status: str
    email_subject: str
    email_body: str
    email_requires_approval: bool
    actions: list[dict[str, str]]
    human_approval_required: bool
    router_provider: str
    router_model: str | None
    router_rationale: str
    router_fallback_reason: str | None
    router_latency_ms: float
    router_usage: Any
