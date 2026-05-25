from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agents.schemas import AgentRequest
from app.agents.service import AgentWorkflowService
from app.db.base import Base
from app.db.models import Ticket
from app.db.session import create_session_factory


def build_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    return session_factory()


async def test_ticket_workflow_classifies_and_simulates_save_without_session() -> None:
    response = await AgentWorkflowService().run(
        AgentRequest(
            message="I did not receive the invoice for my payment.",
            mode="ticket",
        )
    )

    assert response.route == "classify_ticket"
    assert response.ticket is not None
    assert response.ticket.category == "billing"
    assert response.ticket.priority == "normal"
    assert response.ticket.should_escalate is False
    assert response.ticket.id is not None
    assert response.ticket.status == "open"
    assert response.email_draft is not None
    assert response.email_draft.requires_approval is True
    assert response.email_draft.subject == "Re: I did not receive the invoice for my payment."
    assert response.human_approval_required is True
    assert [action.name for action in response.actions] == [
        "classify_ticket",
        "save_ticket",
        "draft_email",
        "send_email",
    ]
    assert response.actions[-1].status == "human_approval_required"


async def test_ticket_workflow_persists_ticket_with_session() -> None:
    session = build_test_session()

    response = await AgentWorkflowService(session=session).run(
        AgentRequest(
            message="I did not receive the invoice for my payment.",
            mode="ticket",
        )
    )

    assert response.ticket is not None
    assert response.ticket.id is not None
    persisted = session.scalar(select(Ticket).where(Ticket.id == response.ticket.id))
    assert persisted is not None
    assert persisted.subject == "I did not receive the invoice for my payment."
    assert persisted.category == "billing"
    assert persisted.priority == "normal"
    assert persisted.status == "open"
    assert response.email_draft is not None
    assert f"Ticket ID: {response.ticket.id}" in response.email_draft.body
    assert response.actions[1].name == "save_ticket"
    assert response.actions[1].status == "completed"
    assert response.actions[2].name == "draft_email"
    assert response.actions[2].status == "completed"


async def test_ticket_workflow_routes_high_priority_to_human_review() -> None:
    response = await AgentWorkflowService().run(
        AgentRequest(
            message="The production API is down and this is critical.",
            mode="ticket",
        )
    )

    assert response.route == "human_escalation"
    assert response.ticket is not None
    assert response.ticket.category == "technical_support"
    assert response.ticket.priority == "high"
    assert response.ticket.should_escalate is True
    assert response.human_approval_required is True
    assert [action.name for action in response.actions] == [
        "classify_ticket",
        "save_ticket",
        "draft_email",
        "send_email",
        "request_human_review",
    ]
    assert response.actions[-1].status == "human_approval_required"
    assert response.email_draft is not None
    assert "escalated this to a human support specialist" in response.email_draft.body


async def test_auto_mode_routes_ticket_signals_to_ticket_workflow() -> None:
    response = await AgentWorkflowService().run(
        AgentRequest(message="Login error after password reset.")
    )

    assert response.route == "classify_ticket"
    assert response.ticket is not None
    assert response.ticket.category == "technical_support"
    assert response.email_draft is not None
