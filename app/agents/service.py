from time import perf_counter
from typing import Any
from uuid import uuid4

import structlog
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.routing import AgentRouter, build_agent_router
from app.agents.schemas import (
    AgentAction,
    AgentEmailDraft,
    AgentRequest,
    AgentResponse,
    AgentRouterMetadata,
    AgentTicketResult,
)
from app.agents.state import AgentState
from app.agents.webhooks import WebhookDispatchService
from app.core.config import get_settings
from app.db.models import Ticket
from app.observability.tracing import Tracer, build_tracer
from app.rag.schemas import ChatRequest, ChatUsageEstimate
from app.rag.service import RagService
from app.tickets.classifier import classify_ticket_text

logger = structlog.get_logger(__name__)


class AgentWorkflowService:
    def __init__(
        self,
        rag_service: RagService | None = None,
        webhook_service: WebhookDispatchService | None = None,
        router: AgentRouter | None = None,
        session: Session | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        settings = get_settings()
        self.rag_service = rag_service or RagService()
        self.webhook_service = webhook_service or WebhookDispatchService()
        self.router = router or build_agent_router(settings)
        self.session = session
        self.tracer = tracer or build_tracer(settings)
        self.workflow = self._build_workflow()

    async def run(self, request: AgentRequest) -> AgentResponse:
        started = perf_counter()
        workflow_run_id = str(uuid4())
        initial_state = {
            "user_message": request.message,
            "workflow_run_id": workflow_run_id,
            "mode": request.mode,
            "top_k": request.top_k,
            "document_ids": request.document_ids,
            "customer_tier": request.customer_tier,
            "actions": [],
            "human_approval_required": False,
        }
        try:
            with self.tracer.span(
                "agent.workflow",
                span_type="agent",
                input={
                    "message_chars": len(request.message),
                    "mode": request.mode,
                    "top_k": request.top_k,
                    "document_filter_count": len(request.document_ids),
                    "customer_tier_present": request.customer_tier is not None,
                },
                metadata={
                    "workflow_run_id": workflow_run_id,
                    "mode": request.mode,
                    "top_k": request.top_k,
                    "document_filter_count": len(request.document_ids),
                    "customer_tier_present": request.customer_tier is not None,
                },
            ) as span:
                state = await self.workflow.ainvoke(initial_state)
                response = self._response_from_state(state)
                span.update(
                    output={
                        "route": response.route,
                        "human_approval_required": response.human_approval_required,
                        "action_count": len(response.actions),
                        "ticket_created": response.ticket is not None,
                        "retrieval_status": response.retrieval_status,
                        "source_count": len(response.sources),
                        "router_provider": state.get("router_provider"),
                        "router_fallback_reason": state.get("router_fallback_reason"),
                    }
                )
        except Exception as exc:
            self._log_workflow_failed(
                request=request,
                workflow_run_id=workflow_run_id,
                latency_ms=(perf_counter() - started) * 1000,
                error_type=type(exc).__name__,
            )
            raise

        self._log_workflow_completed(
            request=request,
            response=response,
            state=state,
            workflow_run_id=workflow_run_id,
            latency_ms=(perf_counter() - started) * 1000,
        )
        return response

    def _build_workflow(self) -> Any:
        workflow = StateGraph(AgentState)
        workflow.add_node("route_request", self._route_request)
        workflow.add_node("answer", self._answer)
        workflow.add_node("classify_ticket", self._classify_ticket)
        workflow.add_node("save_ticket", self._save_ticket)
        workflow.add_node("draft_email", self._draft_email)
        workflow.add_node("notify_n8n_webhook", self._notify_n8n_webhook)
        workflow.add_node("human_escalation", self._human_escalation)

        workflow.set_entry_point("route_request")
        workflow.add_conditional_edges(
            "route_request",
            lambda state: state["route"],
            {
                "answer": "answer",
                "classify_ticket": "classify_ticket",
            },
        )
        workflow.add_edge("answer", END)
        workflow.add_edge("classify_ticket", "save_ticket")
        workflow.add_edge("save_ticket", "draft_email")
        workflow.add_edge("draft_email", "notify_n8n_webhook")
        workflow.add_conditional_edges(
            "notify_n8n_webhook",
            self._next_after_email_draft,
            {
                "human_escalation": "human_escalation",
                "complete": END,
            },
        )
        workflow.add_edge("human_escalation", END)
        return workflow.compile()

    async def _route_request(self, state: AgentState) -> dict[str, object]:
        started = perf_counter()
        with self.tracer.span(
            "agent.router",
            metadata={
                "mode": state.get("mode", "auto"),
                "workflow_run_id": state.get("workflow_run_id"),
            },
        ) as span:
            decision = await self.router.route(
                message=state["user_message"],
                mode=state.get("mode", "auto"),
            )
            span.update(
                output={
                    "route": decision.route,
                    "provider": decision.provider,
                    "model": decision.model,
                    "fallback_reason": decision.fallback_reason,
                    "prompt_tokens": (
                        decision.usage.prompt_tokens if decision.usage is not None else None
                    ),
                    "completion_tokens": (
                        decision.usage.completion_tokens if decision.usage is not None else None
                    ),
                    "total_tokens": (
                        decision.usage.total_tokens if decision.usage is not None else None
                    ),
                    "estimated_cost_usd": (
                        decision.usage.estimated_cost_usd if decision.usage is not None else None
                    ),
                },
                model=decision.model,
                usage_details=_router_langfuse_usage_details(decision.usage),
                cost_details=_router_langfuse_cost_details(decision.usage),
            )
        return {
            "route": decision.route,
            "router_provider": decision.provider,
            "router_model": decision.model,
            "router_rationale": decision.rationale,
            "router_fallback_reason": decision.fallback_reason,
            "router_latency_ms": round((perf_counter() - started) * 1000, 2),
            "router_usage": _router_usage_estimate(decision.usage),
        }

    async def _answer(self, state: AgentState) -> dict[str, object]:
        response = await self.rag_service.answer(
            ChatRequest(
                question=state["user_message"],
                top_k=state.get("top_k"),
                document_ids=state.get("document_ids", []),
            )
        )
        return {
            "route": "answer",
            "answer": response.answer,
            "confidence": response.confidence,
            "retrieval_status": response.retrieval_status,
            "sources": response.sources,
            "usage": response.usage,
        }

    def _classify_ticket(self, state: AgentState) -> dict[str, object]:
        classification = classify_ticket_text(state["user_message"])
        actions = [
            {
                "name": "classify_ticket",
                "status": "simulated",
                "reason": "Ticket classification uses the deterministic local classifier.",
            }
        ]
        return {
            "route": "save_ticket",
            "ticket_category": classification.category,
            "ticket_priority": classification.priority,
            "ticket_should_escalate": classification.should_escalate,
            "ticket_rationale": classification.rationale,
            "ticket_subject": _ticket_subject_from_message(state["user_message"]),
            "ticket_body": state["user_message"],
            "actions": actions,
        }

    async def _save_ticket(self, state: AgentState) -> dict[str, object]:
        ticket = Ticket(
            id=str(uuid4()),
            subject=state["ticket_subject"],
            body=state["ticket_body"],
            category=state["ticket_category"],
            priority=state["ticket_priority"],
            status="open",
        )
        if self.session is not None:
            self.session.add(ticket)
            self.session.commit()

        actions = list(state.get("actions", []))
        actions.append(
            {
                "name": "save_ticket",
                "status": "completed" if self.session is not None else "simulated",
                "reason": (
                    "Ticket persisted to local metadata storage."
                    if self.session is not None
                    else "Ticket persistence skipped because no database session was provided."
                ),
            }
        )
        return {
            "route": "draft_email",
            "ticket_id": ticket.id,
            "ticket_status": ticket.status,
            "actions": actions,
        }

    def _draft_email(self, state: AgentState) -> dict[str, object]:
        email_subject = _email_subject_from_ticket(state["ticket_subject"])
        email_body = _email_body_from_ticket(state)
        actions = list(state.get("actions", []))
        actions.extend(
            [
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
            ]
        )
        return {
            "route": "human_escalation" if state["ticket_should_escalate"] else "classify_ticket",
            "email_subject": email_subject,
            "email_body": email_body,
            "email_requires_approval": True,
            "actions": actions,
            "human_approval_required": True,
        }

    async def _notify_n8n_webhook(self, state: AgentState) -> dict[str, object]:
        dispatch = await self.webhook_service.notify_ticket(
            ticket_id=state.get("ticket_id"),
            ticket_status=state.get("ticket_status"),
            ticket_category=state["ticket_category"],
            ticket_priority=state["ticket_priority"],
            should_escalate=state["ticket_should_escalate"],
            email_requires_approval=state["email_requires_approval"],
        )
        actions = list(state.get("actions", []))
        actions.append(
            {
                "name": dispatch.action_name,
                "status": dispatch.status,
                "reason": dispatch.reason,
            }
        )
        logger.info(
            "agent_n8n_webhook_dispatch",
            workflow_run_id=state.get("workflow_run_id"),
            action_name=dispatch.action_name,
            action_status=dispatch.status,
            payload_summary=dispatch.payload_summary,
            attempts=dispatch.attempts,
            response_status_code=dispatch.response_status_code,
            error_type=dispatch.error_type,
            dispatch_policy={
                "mode": dispatch.dispatch_policy.mode,
                "url_configured": dispatch.dispatch_policy.url_configured,
                "timeout_seconds": dispatch.dispatch_policy.timeout_seconds,
                "max_retries": dispatch.dispatch_policy.max_retries,
                "requires_human_approval": dispatch.dispatch_policy.requires_human_approval,
                "network_dispatch_allowed": (dispatch.dispatch_policy.network_dispatch_allowed),
                "network_dispatch_blockers": list(
                    dispatch.dispatch_policy.network_dispatch_blockers
                ),
            },
        )
        return {"actions": actions}

    def _human_escalation(self, state: AgentState) -> dict[str, object]:
        actions = list(state.get("actions", []))
        actions.append(
            {
                "name": "request_human_review",
                "status": "human_approval_required",
                "reason": "High-priority ticket workflow requires human review.",
            }
        )
        return {
            "route": "human_escalation",
            "actions": actions,
            "human_approval_required": True,
        }

    def _next_after_email_draft(self, state: AgentState) -> str:
        if state.get("ticket_should_escalate"):
            return "human_escalation"
        return "complete"

    def _response_from_state(self, state: AgentState) -> AgentResponse:
        ticket = None
        if "ticket_category" in state:
            ticket = AgentTicketResult(
                id=state.get("ticket_id"),
                status=state.get("ticket_status"),
                category=state["ticket_category"],
                priority=state["ticket_priority"],
                should_escalate=state["ticket_should_escalate"],
                rationale=state["ticket_rationale"],
            )

        email_draft = None
        if "email_subject" in state:
            email_draft = AgentEmailDraft(
                subject=state["email_subject"],
                body=state["email_body"],
                requires_approval=state["email_requires_approval"],
            )

        return AgentResponse(
            route=state["route"],
            answer=state.get("answer"),
            confidence=state.get("confidence"),
            retrieval_status=state.get("retrieval_status"),
            sources=state.get("sources", []),
            usage=state.get("usage"),
            ticket=ticket,
            email_draft=email_draft,
            actions=[
                AgentAction(
                    name=action["name"],
                    status=action["status"],
                    reason=action["reason"],
                )
                for action in state.get("actions", [])
            ],
            human_approval_required=state.get("human_approval_required", False),
            router=AgentRouterMetadata(
                provider=state.get("router_provider", "unknown"),
                model=state.get("router_model"),
                fallback_reason=state.get("router_fallback_reason"),
                latency_ms=state.get("router_latency_ms"),
                usage=state.get("router_usage"),
            ),
        )

    def _log_workflow_completed(
        self,
        *,
        request: AgentRequest,
        response: AgentResponse,
        state: AgentState,
        workflow_run_id: str,
        latency_ms: float,
    ) -> None:
        logger.info(
            "agent_workflow_completed",
            workflow_run_id=workflow_run_id,
            route=response.route,
            mode=request.mode,
            latency_ms=round(latency_ms, 2),
            top_k=request.top_k,
            document_filter_count=len(request.document_ids),
            customer_tier_present=request.customer_tier is not None,
            human_approval_required=response.human_approval_required,
            router_provider=state.get("router_provider"),
            router_model=state.get("router_model"),
            router_rationale=state.get("router_rationale"),
            router_fallback_reason=state.get("router_fallback_reason"),
            router_latency_ms=state.get("router_latency_ms"),
            router_prompt_tokens=(
                state["router_usage"].prompt_tokens
                if state.get("router_usage") is not None
                else None
            ),
            router_completion_tokens=(
                state["router_usage"].completion_tokens
                if state.get("router_usage") is not None
                else None
            ),
            router_total_tokens=(
                state["router_usage"].total_tokens
                if state.get("router_usage") is not None
                else None
            ),
            router_estimated_cost_usd=(
                state["router_usage"].estimated_cost_usd
                if state.get("router_usage") is not None
                else None
            ),
            action_names=[action.name for action in response.actions],
            action_statuses=[
                {"name": action.name, "status": action.status} for action in response.actions
            ],
            ticket_id=response.ticket.id if response.ticket is not None else None,
            ticket_status=response.ticket.status if response.ticket is not None else None,
            ticket_category=response.ticket.category if response.ticket is not None else None,
            ticket_priority=response.ticket.priority if response.ticket is not None else None,
            retrieval_status=response.retrieval_status,
            source_count=len(response.sources),
        )

    def _log_workflow_failed(
        self,
        *,
        request: AgentRequest,
        workflow_run_id: str,
        latency_ms: float,
        error_type: str,
    ) -> None:
        logger.info(
            "agent_workflow_failed",
            workflow_run_id=workflow_run_id,
            mode=request.mode,
            latency_ms=round(latency_ms, 2),
            top_k=request.top_k,
            document_filter_count=len(request.document_ids),
            customer_tier_present=request.customer_tier is not None,
            error_type=error_type,
        )


def _ticket_subject_from_message(message: str) -> str:
    first_line = message.strip().splitlines()[0]
    return first_line[:120] or "Support request"


def _router_usage_estimate(usage: Any) -> ChatUsageEstimate | None:
    if usage is None:
        return None
    return ChatUsageEstimate(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost_usd=usage.estimated_cost_usd,
    )


def _router_langfuse_usage_details(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    return {
        "input": usage.prompt_tokens,
        "output": usage.completion_tokens,
        "total": usage.total_tokens,
    }


def _router_langfuse_cost_details(usage: Any) -> dict[str, float] | None:
    if usage is None or usage.estimated_cost_usd is None:
        return None
    return {"total": usage.estimated_cost_usd}


def _email_subject_from_ticket(ticket_subject: str) -> str:
    return f"Re: {ticket_subject}"[:160]


def _email_body_from_ticket(state: AgentState) -> str:
    priority_sentence = (
        "I have escalated this to a human support specialist for review."
        if state["ticket_should_escalate"]
        else "I have routed this to the support team for follow-up."
    )
    return (
        "Hi,\n\n"
        "Thanks for contacting support. "
        f"We received your request about: {state['ticket_subject']}.\n\n"
        f"Ticket ID: {state['ticket_id']}\n"
        f"Category: {state['ticket_category']}\n"
        f"Priority: {state['ticket_priority']}\n\n"
        f"{priority_sentence}\n\n"
        "A support teammate should review this draft before it is sent.\n\n"
        "Regards,\n"
        "Support Team"
    )
