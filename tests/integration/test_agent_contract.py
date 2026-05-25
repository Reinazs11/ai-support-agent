from fastapi.testclient import TestClient

from app.main import create_app


def test_agent_answer_contract_uses_rag_response_shape() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/respond",
        json={"message": "What is the refund policy?", "mode": "answer"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "answer"
    assert body["retrieval_status"] == "not_configured"
    assert body["confidence"] == "low"
    assert body["sources"] == []
    assert body["answer"]
    assert body["ticket"] is None
    assert body["human_approval_required"] is False


def test_agent_ticket_contract_keeps_actions_simulated() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/agent/respond",
        json={
            "message": "The production API is down and this is critical.",
            "mode": "ticket",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "human_escalation"
    assert body["ticket"]["category"] == "technical_support"
    assert body["ticket"]["priority"] == "high"
    assert body["ticket"]["should_escalate"] is True
    assert body["human_approval_required"] is True
    assert body["actions"] == [
        {
            "name": "classify_ticket",
            "status": "simulated",
            "reason": "Ticket classification is recorded in workflow state only.",
        },
        {
            "name": "request_human_review",
            "status": "human_approval_required",
            "reason": "High-priority ticket workflow requires human review.",
        },
    ]
