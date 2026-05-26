from app.agents.webhooks import (
    WebhookDispatchService,
    WebhookHttpResponse,
)
from app.core.config import Settings


class FakeWebhookHttpClient:
    def __init__(self, responses: list[WebhookHttpResponse | Exception]) -> None:
        self.responses = responses
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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


async def test_webhook_simulation_reports_policy_without_network_dispatch() -> None:
    service = WebhookDispatchService(
        settings=Settings(
            n8n_webhook_mode="simulated",
            n8n_webhook_url="https://n8n.example.test/webhook/support",
            n8n_webhook_timeout_seconds=3,
            n8n_webhook_max_retries=2,
            n8n_webhook_requires_human_approval=True,
        )
    )

    dispatch = await service.notify_ticket(
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


async def test_webhook_simulation_disabled_policy_still_does_not_complete_action() -> None:
    service = WebhookDispatchService(
        settings=Settings(
            n8n_webhook_mode="disabled",
            n8n_webhook_url="",
            n8n_webhook_requires_human_approval=True,
        )
    )

    dispatch = await service.notify_ticket(
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
    service = WebhookDispatchService(
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


async def test_live_webhook_dispatch_posts_safe_payload() -> None:
    http_client = FakeWebhookHttpClient([WebhookHttpResponse(status_code=200)])
    service = WebhookDispatchService(
        settings=Settings(
            n8n_webhook_mode="live",
            n8n_webhook_url="https://n8n.example.test/webhook/support",
            n8n_webhook_timeout_seconds=4,
            n8n_webhook_max_retries=0,
            n8n_webhook_requires_human_approval=False,
        ),
        http_client=http_client,
    )

    dispatch = await service.notify_ticket(
        ticket_id="ticket-1",
        ticket_status="open",
        ticket_category="billing",
        ticket_priority="normal",
        should_escalate=False,
        email_requires_approval=True,
    )

    assert dispatch.status == "completed"
    assert dispatch.reason == "n8n webhook notification sent successfully."
    assert dispatch.attempts == 1
    assert dispatch.response_status_code == 200
    assert dispatch.error_type is None
    assert dispatch.dispatch_policy.network_dispatch_allowed is True
    assert dispatch.dispatch_policy.network_dispatch_blockers == ()
    assert http_client.requests == [
        {
            "url": "https://n8n.example.test/webhook/support",
            "payload": {
                "ticket_id": "ticket-1",
                "ticket_status": "open",
                "ticket_category": "billing",
                "ticket_priority": "normal",
                "should_escalate": False,
                "email_requires_approval": True,
            },
            "timeout_seconds": 4,
        }
    ]


async def test_live_webhook_dispatch_is_blocked_by_human_approval() -> None:
    http_client = FakeWebhookHttpClient([WebhookHttpResponse(status_code=200)])
    service = WebhookDispatchService(
        settings=Settings(
            n8n_webhook_mode="live",
            n8n_webhook_url="https://n8n.example.test/webhook/support",
            n8n_webhook_requires_human_approval=True,
        ),
        http_client=http_client,
    )

    dispatch = await service.notify_ticket(
        ticket_id="ticket-1",
        ticket_status="open",
        ticket_category="billing",
        ticket_priority="high",
        should_escalate=True,
        email_requires_approval=True,
    )

    assert dispatch.status == "human_approval_required"
    assert dispatch.reason == (
        "n8n webhook dispatch requires human approval; no external request was sent."
    )
    assert dispatch.attempts == 0
    assert dispatch.dispatch_policy.network_dispatch_allowed is False
    assert dispatch.dispatch_policy.network_dispatch_blockers == ("human_approval_required",)
    assert http_client.requests == []


async def test_live_webhook_dispatch_retries_and_reports_failure() -> None:
    http_client = FakeWebhookHttpClient(
        [
            RuntimeError("temporary network failure"),
            WebhookHttpResponse(status_code=500),
        ]
    )
    service = WebhookDispatchService(
        settings=Settings(
            n8n_webhook_mode="live",
            n8n_webhook_url="https://n8n.example.test/webhook/support",
            n8n_webhook_max_retries=1,
            n8n_webhook_requires_human_approval=False,
        ),
        http_client=http_client,
    )

    dispatch = await service.notify_ticket(
        ticket_id="ticket-1",
        ticket_status="open",
        ticket_category="technical_support",
        ticket_priority="high",
        should_escalate=True,
        email_requires_approval=True,
    )

    assert dispatch.status == "failed"
    assert dispatch.reason == "n8n webhook dispatch returned a non-success status code."
    assert dispatch.attempts == 2
    assert dispatch.response_status_code == 500
    assert dispatch.error_type == "HttpStatusError"
    assert len(http_client.requests) == 2
