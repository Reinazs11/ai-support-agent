from typing import Any
from uuid import uuid4

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.schemas import AgentAction, AgentRequest, AgentResponse, AgentTicketResult
from app.agents.state import AgentState
from app.db.models import Ticket
from app.rag.schemas import ChatRequest
from app.rag.service import RagService
from app.tickets.classifier import classify_ticket_text

TICKET_SIGNAL_TERMS = {
    "billing",
    "bug",
    "critical",
    "down",
    "error",
    "failure",
    "invoice",
    "login",
    "payment",
    "password",
    "urgent",
}


class AgentWorkflowService:
    def __init__(
        self,
        rag_service: RagService | None = None,
        session: Session | None = None,
    ) -> None:
        self.rag_service = rag_service or RagService()
        self.session = session
        self.workflow = self._build_workflow()

    async def run(self, request: AgentRequest) -> AgentResponse:
        state = await self.workflow.ainvoke(
            {
                "user_message": request.message,
                "mode": request.mode,
                "top_k": request.top_k,
                "document_ids": request.document_ids,
                "customer_tier": request.customer_tier,
                "actions": [],
                "human_approval_required": False,
            }
        )
        return self._response_from_state(state)

    def _build_workflow(self) -> Any:
        workflow = StateGraph(AgentState)
        workflow.add_node("route_request", self._route_request)
        workflow.add_node("answer", self._answer)
        workflow.add_node("classify_ticket", self._classify_ticket)
        workflow.add_node("save_ticket", self._save_ticket)
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
        workflow.add_conditional_edges(
            "save_ticket",
            self._next_after_ticket_save,
            {
                "human_escalation": "human_escalation",
                "complete": END,
            },
        )
        workflow.add_edge("human_escalation", END)
        return workflow.compile()

    def _route_request(self, state: AgentState) -> dict[str, str]:
        mode = state.get("mode", "auto")
        if mode == "answer":
            return {"route": "answer"}
        if mode == "ticket":
            return {"route": "classify_ticket"}
        if _looks_like_ticket(state["user_message"]):
            return {"route": "classify_ticket"}
        return {"route": "answer"}

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
            "route": "human_escalation"
            if state["ticket_should_escalate"]
            else "classify_ticket",
            "ticket_id": ticket.id,
            "ticket_status": ticket.status,
            "actions": actions,
        }

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

    def _next_after_ticket_save(self, state: AgentState) -> str:
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

        return AgentResponse(
            route=state["route"],
            answer=state.get("answer"),
            confidence=state.get("confidence"),
            retrieval_status=state.get("retrieval_status"),
            sources=state.get("sources", []),
            usage=state.get("usage"),
            ticket=ticket,
            actions=[
                AgentAction(
                    name=action["name"],
                    status=action["status"],
                    reason=action["reason"],
                )
                for action in state.get("actions", [])
            ],
            human_approval_required=state.get("human_approval_required", False),
        )


def _looks_like_ticket(message: str) -> bool:
    normalized = message.lower()
    return any(term in normalized for term in TICKET_SIGNAL_TERMS)


def _ticket_subject_from_message(message: str) -> str:
    first_line = message.strip().splitlines()[0]
    return first_line[:120] or "Support request"
