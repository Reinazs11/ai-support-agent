from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class WebhookDispatchPolicy:
    mode: str
    url_configured: bool
    timeout_seconds: float
    max_retries: int
    requires_human_approval: bool


@dataclass(frozen=True)
class SimulatedWebhookDispatch:
    action_name: str
    status: str
    reason: str
    payload_summary: dict[str, object]
    dispatch_policy: WebhookDispatchPolicy


class WebhookSimulationService:
    """Builds safe webhook simulation metadata without sending network requests."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

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
        policy = self.dispatch_policy()
        return SimulatedWebhookDispatch(
            action_name="notify_n8n_webhook",
            status="simulated",
            reason=self._simulation_reason(policy),
            payload_summary={
                "ticket_id": ticket_id,
                "ticket_status": ticket_status,
                "ticket_category": ticket_category,
                "ticket_priority": ticket_priority,
                "should_escalate": should_escalate,
                "email_requires_approval": email_requires_approval,
            },
            dispatch_policy=policy,
        )

    def dispatch_policy(self) -> WebhookDispatchPolicy:
        return WebhookDispatchPolicy(
            mode=self.settings.n8n_webhook_mode,
            url_configured=bool(self.settings.n8n_webhook_url),
            timeout_seconds=self.settings.n8n_webhook_timeout_seconds,
            max_retries=self.settings.n8n_webhook_max_retries,
            requires_human_approval=self.settings.n8n_webhook_requires_human_approval,
        )

    def _simulation_reason(self, policy: WebhookDispatchPolicy) -> str:
        if policy.mode == "disabled":
            return "n8n webhook notification disabled; no external request was sent."
        return "n8n webhook notification simulated locally; no external request was sent."
