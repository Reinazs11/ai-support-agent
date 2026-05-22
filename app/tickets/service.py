from app.tickets.classifier import classify_ticket_text
from app.tickets.schemas import TicketClassificationRequest, TicketClassificationResponse


class TicketService:
    def classify(self, request: TicketClassificationRequest) -> TicketClassificationResponse:
        text = f"{request.subject}\n{request.body}"
        classification = classify_ticket_text(text)
        return TicketClassificationResponse(
            category=classification.category,
            priority=classification.priority,
            should_escalate=classification.should_escalate,
            rationale=classification.rationale,
        )
