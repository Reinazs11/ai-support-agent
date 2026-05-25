from app.agents.schemas import AgentRequest
from app.agents.service import AgentWorkflowService


async def test_ticket_workflow_classifies_without_external_side_effects() -> None:
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
    assert response.human_approval_required is False
    assert [action.name for action in response.actions] == ["classify_ticket"]
    assert all(action.status == "simulated" for action in response.actions)


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
        "request_human_review",
    ]
    assert response.actions[-1].status == "human_approval_required"


async def test_auto_mode_routes_ticket_signals_to_ticket_workflow() -> None:
    response = await AgentWorkflowService().run(
        AgentRequest(message="Login error after password reset.")
    )

    assert response.route == "classify_ticket"
    assert response.ticket is not None
    assert response.ticket.category == "technical_support"
