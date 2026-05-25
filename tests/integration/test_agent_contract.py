from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Ticket
from app.db.session import create_session_factory, get_db_session
from app.main import create_app


def build_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


def build_test_client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    return TestClient(app)


def test_agent_answer_contract_uses_rag_response_shape() -> None:
    session = build_test_session()
    client = build_test_client(session)

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


def test_agent_ticket_contract_persists_ticket_and_keeps_external_actions_controlled() -> None:
    session = build_test_session()
    client = build_test_client(session)

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
    assert body["ticket"]["id"]
    assert body["ticket"]["status"] == "open"
    assert body["ticket"]["category"] == "technical_support"
    assert body["ticket"]["priority"] == "high"
    assert body["ticket"]["should_escalate"] is True
    assert body["email_draft"]["subject"] == "Re: The production API is down and this is critical."
    assert body["email_draft"]["requires_approval"] is True
    assert f"Ticket ID: {body['ticket']['id']}" in body["email_draft"]["body"]
    assert body["human_approval_required"] is True
    assert body["actions"] == [
        {
            "name": "classify_ticket",
            "status": "simulated",
            "reason": "Ticket classification uses the deterministic local classifier.",
        },
        {
            "name": "save_ticket",
            "status": "completed",
            "reason": "Ticket persisted to local metadata storage.",
        },
        {
            "name": "draft_email",
            "status": "completed",
            "reason": "Email draft generated locally from ticket context.",
        },
        {
            "name": "send_email",
            "status": "human_approval_required",
            "reason": "Workflow does not send external communications automatically.",
        },
        {
            "name": "request_human_review",
            "status": "human_approval_required",
            "reason": "High-priority ticket workflow requires human review.",
        },
    ]

    persisted = session.scalar(select(Ticket).where(Ticket.id == body["ticket"]["id"]))
    assert persisted is not None
    assert persisted.status == "open"
    assert persisted.priority == "high"
