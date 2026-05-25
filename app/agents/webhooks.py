from dataclasses import dataclass


@dataclass(frozen=True)
class SimulatedWebhookDispatch:
    action_name: str
    status: str
    reason: str
    payload_summary: dict[str, object]


class WebhookSimulationService:
    """Builds safe webhook simulation metadata without sending network requests."""

    def simulate_ticket_notification(
        self,
        *,
        ticket_id: str | None,
        ticket_status: str | None,
        ticket_category: str,
        ticket_priority: str,
        should_escalate: bool,
        email_requires_approval: bool,
    ) -> SimulatedWebhookDispatch:
        return SimulatedWebhookDispatch(
            action_name="notify_n8n_webhook",
            status="simulated",
            reason="n8n webhook notification simulated locally; no external request was sent.",
            payload_summary={
                "ticket_id": ticket_id,
                "ticket_status": ticket_status,
                "ticket_category": ticket_category,
                "ticket_priority": ticket_priority,
                "should_escalate": should_escalate,
                "email_requires_approval": email_requires_approval,
            },
        )
