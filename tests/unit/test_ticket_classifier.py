from app.tickets.classifier import classify_ticket_text


def test_classify_billing_ticket() -> None:
    result = classify_ticket_text("I did not receive the invoice for my payment")

    assert result.category == "billing"
    assert result.priority == "normal"


def test_classify_urgent_ticket_escalates() -> None:
    result = classify_ticket_text("API is down, critical issue")

    assert result.category == "technical_support"
    assert result.priority == "high"
    assert result.should_escalate is True
