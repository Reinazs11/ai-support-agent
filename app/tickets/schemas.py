from pydantic import BaseModel, Field


class TicketClassificationRequest(BaseModel):
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    customer_tier: str | None = None


class TicketClassificationResponse(BaseModel):
    category: str
    priority: str
    should_escalate: bool
    rationale: str
