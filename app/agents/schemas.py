from typing import Literal

from pydantic import BaseModel, Field

from app.rag.schemas import ChatUsageEstimate, SourceCitation


class AgentRequest(BaseModel):
    message: str = Field(min_length=1)
    mode: Literal["auto", "answer", "ticket"] = "auto"
    top_k: int | None = Field(default=None, ge=1, le=20)
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    customer_tier: str | None = None


class AgentTicketResult(BaseModel):
    id: str | None = None
    status: str | None = None
    category: str
    priority: str
    should_escalate: bool
    rationale: str


class AgentAction(BaseModel):
    name: str
    status: Literal["completed", "simulated", "human_approval_required", "failed"]
    reason: str


class AgentEmailDraft(BaseModel):
    subject: str
    body: str
    requires_approval: bool = True


class AgentResponse(BaseModel):
    route: Literal["answer", "classify_ticket", "save_ticket", "draft_email", "human_escalation"]
    answer: str | None = None
    confidence: str | None = None
    retrieval_status: str | None = None
    sources: list[SourceCitation] = Field(default_factory=list)
    usage: ChatUsageEstimate | None = None
    ticket: AgentTicketResult | None = None
    email_draft: AgentEmailDraft | None = None
    actions: list[AgentAction] = Field(default_factory=list)
    human_approval_required: bool = False
