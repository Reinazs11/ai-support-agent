from app.agents.webhooks import WebhookSimulationService
from app.core.config import Settings


def test_webhook_simulation_reports_policy_without_network_dispatch() -> None:
    service = WebhookSimulationService(
        settings=Settings(
            n8n_webhook_mode="simulated",
            n8n_webhook_url="https://n8n.example.test/webhook/support",
            n8n_webhook_timeout_seconds=3,
            n8n_webhook_max_retries=2,
            n8n_webhook_requires_human_approval=True,
        )
    )

    dispatch = service.simulate_ticket_notification(
        ticket_id="ticket-1",
        ticket_status="open",
        ticket_category="billing",
        ticket_priority="high",
        should_escalate=True,
        email_requires_approval=True,
    )

    assert dispatch.action_name == "notify_n8n_webhook"
    assert dispatch.status == "simulated"
    assert dispatch.reason == (
        "n8n webhook notification simulated locally; no external request was sent."
    )
    assert dispatch.payload_summary == {
        "ticket_id": "ticket-1",
        "ticket_status": "open",
        "ticket_category": "billing",
        "ticket_priority": "high",
        "should_escalate": True,
        "email_requires_approval": True,
    }
    assert dispatch.dispatch_policy.mode == "simulated"
    assert dispatch.dispatch_policy.url_configured is True
    assert dispatch.dispatch_policy.timeout_seconds == 3
    assert dispatch.dispatch_policy.max_retries == 2
    assert dispatch.dispatch_policy.requires_human_approval is True
    assert dispatch.dispatch_policy.network_dispatch_allowed is False
    assert dispatch.dispatch_policy.network_dispatch_blockers == (
        "mode_simulated",
        "human_approval_required",
    )


def test_webhook_simulation_disabled_policy_still_does_not_complete_action() -> None:
    service = WebhookSimulationService(
        settings=Settings(
            n8n_webhook_mode="disabled",
            n8n_webhook_url="",
            n8n_webhook_requires_human_approval=True,
        )
    )

    dispatch = service.simulate_ticket_notification(
        ticket_id=None,
        ticket_status=None,
        ticket_category="technical_support",
        ticket_priority="normal",
        should_escalate=False,
        email_requires_approval=True,
    )

    assert dispatch.status == "simulated"
    assert dispatch.reason == "n8n webhook notification disabled; no external request was sent."
    assert dispatch.dispatch_policy.mode == "disabled"
    assert dispatch.dispatch_policy.url_configured is False
    assert dispatch.dispatch_policy.network_dispatch_allowed is False
    assert dispatch.dispatch_policy.network_dispatch_blockers == (
        "mode_disabled",
        "missing_webhook_url",
        "human_approval_required",
    )


def test_webhook_policy_reports_missing_url_without_human_approval_blocker() -> None:
    service = WebhookSimulationService(
        settings=Settings(
            n8n_webhook_mode="simulated",
            n8n_webhook_url=" ",
            n8n_webhook_requires_human_approval=False,
        )
    )

    policy = service.dispatch_policy()

    assert policy.url_configured is False
    assert policy.network_dispatch_allowed is False
    assert policy.network_dispatch_blockers == ("mode_simulated", "missing_webhook_url")
