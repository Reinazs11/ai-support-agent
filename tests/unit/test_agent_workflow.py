import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agents.routing import (
    AgentRouteDecision,
    AgentRouterProviderError,
    AgentRouteTokenUsage,
    FallbackAgentRouter,
)
from app.agents.schemas import AgentRequest
from app.agents.service import AgentWorkflowService
from app.agents.webhooks import WebhookDispatchService, WebhookHttpResponse
from app.core.config import Settings
from app.db.base import Base
from app.db.models import Ticket
from app.db.session import create_session_factory
from app.rag.schemas import ChatResponse


class CapturingLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []

    def info(self, event: str, **metadata: object) -> None:
        self.records.append((event, metadata))


class FailingRagService:
    async def answer(self, request: object) -> object:
        raise ValueError("boom")


class SimpleRagService:
    async def answer(self, request: object) -> ChatResponse:
        return ChatResponse(
            answer="RAG answer",
            confidence="low",
            retrieval_status="generated",
        )


class FakeRouteModelService:
    model = "fake-router"

    def __init__(
        self,
        decision: AgentRouteDecision | None = None,
        error: Exception | None = None,
    ) -> None:
        self.decision = decision
        self.error = error
        self.messages: list[str] = []

    async def classify_route(self, message: str) -> AgentRouteDecision:
        self.messages.append(message)
        if self.error is not None:
            raise self.error
        if self.decision is None:
            raise AgentRouterProviderError("No fake decision configured.")
        return self.decision


class FakeWebhookHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def post_json(
        self,
        *,
        url: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> WebhookHttpResponse:
        self.requests.append(
            {"url": url, "payload": payload, "timeout_seconds": timeout_seconds}
        )
        return WebhookHttpResponse(status_code=200)


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


async def test_llm_router_can_route_auto_mode_to_ticket_workflow() -> None:
    route_model = FakeRouteModelService(
        decision=AgentRouteDecision(
            route="classify_ticket",
            provider="fake-llm",
            rationale="support_follow_up",
            model="fake-router",
            usage=AgentRouteTokenUsage(
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
                estimated_cost_usd=0.000045,
            ),
        )
    )
    router = FallbackAgentRouter(primary=route_model)

    response = await AgentWorkflowService(router=router).run(
        AgentRequest(message="Please have the support team follow up with me.")
    )

    assert route_model.messages == ["Please have the support team follow up with me."]
    assert response.route == "classify_ticket"
    assert response.ticket is not None
    assert response.email_draft is not None
    assert response.router is not None
    assert response.router.provider == "fake-llm"
    assert response.router.model == "fake-router"
    assert response.router.usage is not None
    assert response.router.usage.prompt_tokens == 100
    assert response.router.usage.completion_tokens == 20
    assert response.router.usage.total_tokens == 120
    assert response.router.usage.estimated_cost_usd == 0.000045


async def test_llm_router_failure_falls_back_to_deterministic_routing(
    monkeypatch,
) -> None:
    capture = CapturingLogger()
    monkeypatch.setattr("app.agents.service.logger", capture)
    route_model = FakeRouteModelService(
        error=AgentRouterProviderError("provider unavailable")
    )
    router = FallbackAgentRouter(primary=route_model)

    response = await AgentWorkflowService(router=router).run(
        AgentRequest(message="Login error after password reset.")
    )

    assert response.route == "classify_ticket"
    assert response.ticket is not None
    event, metadata = capture.records[-1]
    assert event == "agent_workflow_completed"
    assert metadata["router_provider"] == "deterministic"
    assert metadata["router_model"] == "fake-router"
    assert metadata["router_rationale"] == "ticket_signal_terms"
    assert metadata["router_fallback_reason"] == "AgentRouterProviderError"
    assert metadata["router_latency_ms"] >= 0
    assert metadata["router_prompt_tokens"] is None
    assert metadata["router_estimated_cost_usd"] is None


async def test_llm_router_invalid_answer_falls_back_to_answer_route() -> None:
    route_model = FakeRouteModelService(
        error=AgentRouterProviderError("invalid route response")
    )
    router = FallbackAgentRouter(primary=route_model)

    response = await AgentWorkflowService(
        rag_service=SimpleRagService(),
        router=router,
    ).run(AgentRequest(message="What does the refund policy say?"))

    assert response.route == "answer"
    assert response.answer == "RAG answer"
    assert response.ticket is None


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
    assert metadata["router_provider"] == "deterministic"
    assert metadata["router_model"] is None
    assert metadata["router_rationale"] == "explicit_ticket_mode"
    assert metadata["router_fallback_reason"] is None
    assert metadata["router_latency_ms"] >= 0
    assert metadata["router_prompt_tokens"] is None
    assert metadata["router_completion_tokens"] is None
    assert metadata["router_total_tokens"] is None
    assert metadata["router_estimated_cost_usd"] is None
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
    assert webhook_event == "agent_n8n_webhook_dispatch"
    assert webhook_metadata["action_name"] == "notify_n8n_webhook"
    assert webhook_metadata["action_status"] == "simulated"
    assert webhook_metadata["attempts"] == 0
    assert webhook_metadata["response_status_code"] is None
    assert webhook_metadata["error_type"] is None
    assert webhook_metadata["payload_summary"]["ticket_id"] == response.ticket.id
    assert webhook_metadata["payload_summary"]["ticket_category"] == "billing"
    assert webhook_metadata["dispatch_policy"]["mode"] == "simulated"
    assert webhook_metadata["dispatch_policy"]["requires_human_approval"] is True
    assert webhook_metadata["dispatch_policy"]["network_dispatch_allowed"] is False
    assert webhook_metadata["dispatch_policy"]["network_dispatch_blockers"] == [
        "mode_simulated",
        "missing_webhook_url",
        "human_approval_required",
    ]
    assert sensitive_message not in serialized_webhook_metadata
    assert "ABC123" not in serialized_webhook_metadata


async def test_ticket_workflow_can_complete_live_n8n_dispatch_without_logging_url(
    monkeypatch,
) -> None:
    capture = CapturingLogger()
    monkeypatch.setattr("app.agents.service.logger", capture)
    http_client = FakeWebhookHttpClient()
    webhook_url = "https://n8n.example.test/webhook/support"
    webhook_service = WebhookDispatchService(
        settings=Settings(
            n8n_webhook_mode="live",
            n8n_webhook_url=webhook_url,
            n8n_webhook_timeout_seconds=4,
            n8n_webhook_requires_human_approval=False,
        ),
        http_client=http_client,
    )
    sensitive_message = "Invoice problem with private token LIVE123."

    response = await AgentWorkflowService(
        session=build_test_session(),
        webhook_service=webhook_service,
    ).run(AgentRequest(message=sensitive_message, mode="ticket"))

    action_statuses = {action.name: action.status for action in response.actions}
    assert action_statuses["notify_n8n_webhook"] == "completed"
    assert len(http_client.requests) == 1
    assert http_client.requests[0]["url"] == webhook_url

    webhook_event, webhook_metadata = capture.records[0]
    serialized_webhook_metadata = json.dumps(webhook_metadata)
    assert webhook_event == "agent_n8n_webhook_dispatch"
    assert webhook_metadata["action_status"] == "completed"
    assert webhook_metadata["attempts"] == 1
    assert webhook_metadata["response_status_code"] == 200
    assert webhook_metadata["dispatch_policy"]["mode"] == "live"
    assert webhook_metadata["dispatch_policy"]["network_dispatch_allowed"] is True
    assert webhook_metadata["dispatch_policy"]["network_dispatch_blockers"] == []
    assert webhook_url not in serialized_webhook_metadata
    assert sensitive_message not in serialized_webhook_metadata
    assert "LIVE123" not in serialized_webhook_metadata


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
