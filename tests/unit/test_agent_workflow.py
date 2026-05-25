import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agents.schemas import AgentRequest
from app.agents.service import AgentWorkflowService
from app.db.base import Base
from app.db.models import Ticket
from app.db.session import create_session_factory


class CapturingLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []

    def info(self, event: str, **metadata: object) -> None:
        self.records.append((event, metadata))


class FailingRagService:
    async def answer(self, request: object) -> object:
        raise ValueError("boom")


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
        "notify_n8n_webhook",
    ]
    action_statuses = {action.name: action.status for action in response.actions}
    assert action_statuses["send_email"] == "human_approval_required"
    assert action_statuses["notify_n8n_webhook"] == "simulated"


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
    assert response.actions[4].name == "notify_n8n_webhook"
    assert response.actions[4].status == "simulated"


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
        "notify_n8n_webhook",
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


async def test_ticket_workflow_logs_structured_audit_without_message_content(
    monkeypatch,
) -> None:
    capture = CapturingLogger()
    monkeypatch.setattr("app.agents.service.logger", capture)
    sensitive_message = "Secret account token ABC123 invoice problem."

    response = await AgentWorkflowService(session=build_test_session()).run(
        AgentRequest(message=sensitive_message, mode="ticket", customer_tier="enterprise")
    )

    assert response.ticket is not None
    event, metadata = capture.records[-1]
    serialized_metadata = json.dumps(metadata)
    assert event == "agent_workflow_completed"
    assert metadata["route"] == "classify_ticket"
    assert metadata["mode"] == "ticket"
    assert metadata["workflow_run_id"]
    assert metadata["human_approval_required"] is True
    assert metadata["ticket_id"] == response.ticket.id
    assert metadata["ticket_category"] == "billing"
    assert metadata["ticket_priority"] == "normal"
    assert metadata["customer_tier_present"] is True
    assert metadata["action_names"] == [
        "classify_ticket",
        "save_ticket",
        "draft_email",
        "send_email",
        "notify_n8n_webhook",
    ]
    action_statuses = {
        action_status["name"]: action_status["status"]
        for action_status in metadata["action_statuses"]
    }
    assert action_statuses["send_email"] == "human_approval_required"
    assert action_statuses["notify_n8n_webhook"] == "simulated"
    assert "latency_ms" in metadata
    assert sensitive_message not in serialized_metadata
    assert "ABC123" not in serialized_metadata

    webhook_event, webhook_metadata = capture.records[0]
    serialized_webhook_metadata = json.dumps(webhook_metadata)
    assert webhook_event == "agent_n8n_webhook_simulated"
    assert webhook_metadata["action_name"] == "notify_n8n_webhook"
    assert webhook_metadata["action_status"] == "simulated"
    assert webhook_metadata["payload_summary"]["ticket_id"] == response.ticket.id
    assert webhook_metadata["payload_summary"]["ticket_category"] == "billing"
    assert webhook_metadata["dispatch_policy"]["mode"] == "simulated"
    assert webhook_metadata["dispatch_policy"]["requires_human_approval"] is True
    assert sensitive_message not in serialized_webhook_metadata
    assert "ABC123" not in serialized_webhook_metadata


async def test_agent_workflow_failure_logs_error_type_without_message_content(
    monkeypatch,
) -> None:
    capture = CapturingLogger()
    monkeypatch.setattr("app.agents.service.logger", capture)
    sensitive_message = "Private customer question with token XYZ789."

    with pytest.raises(ValueError, match="boom"):
        await AgentWorkflowService(rag_service=FailingRagService()).run(
            AgentRequest(message=sensitive_message, mode="answer", document_ids=["doc-1"])
        )

    assert len(capture.records) == 1
    event, metadata = capture.records[0]
    serialized_metadata = json.dumps(metadata)
    assert event == "agent_workflow_failed"
    assert metadata["mode"] == "answer"
    assert metadata["workflow_run_id"]
    assert metadata["document_filter_count"] == 1
    assert metadata["error_type"] == "ValueError"
    assert "latency_ms" in metadata
    assert sensitive_message not in serialized_metadata
    assert "XYZ789" not in serialized_metadata
