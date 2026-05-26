from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class WebhookDispatchPolicy:
    mode: str
    url_configured: bool
    timeout_seconds: float
    max_retries: int
    requires_human_approval: bool
    network_dispatch_allowed: bool
    network_dispatch_blockers: tuple[str, ...]


@dataclass(frozen=True)
class WebhookDispatch:
    action_name: str
    status: str
    reason: str
    payload_summary: dict[str, object]
    dispatch_policy: WebhookDispatchPolicy
    attempts: int
    response_status_code: int | None = None
    error_type: str | None = None


@dataclass(frozen=True)
class WebhookHttpResponse:
    status_code: int


class WebhookHttpClient(Protocol):
    async def post_json(
        self,
        *,
        url: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> WebhookHttpResponse:
        pass


class HttpxWebhookHttpClient:
    async def post_json(
        self,
        *,
        url: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> WebhookHttpResponse:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload)
        return WebhookHttpResponse(status_code=response.status_code)


class WebhookDispatchService:
    """Dispatches or safely gates n8n webhook notifications."""

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: WebhookHttpClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client or HttpxWebhookHttpClient()

    async def notify_ticket(
        self,
        *,
        ticket_id: str | None,
        ticket_status: str | None,
        ticket_category: str,
        ticket_priority: str,
        should_escalate: bool,
        email_requires_approval: bool,
    ) -> WebhookDispatch:
        policy = self.dispatch_policy()
        payload_summary = {
            "ticket_id": ticket_id,
            "ticket_status": ticket_status,
            "ticket_category": ticket_category,
            "ticket_priority": ticket_priority,
            "should_escalate": should_escalate,
            "email_requires_approval": email_requires_approval,
        }
        if not policy.network_dispatch_allowed:
            return WebhookDispatch(
                action_name="notify_n8n_webhook",
                status=self._blocked_status(policy),
                reason=self._blocked_reason(policy),
                payload_summary=payload_summary,
                dispatch_policy=policy,
                attempts=0,
            )

        return await self._dispatch_live(payload_summary=payload_summary, policy=policy)

    def dispatch_policy(self) -> WebhookDispatchPolicy:
        mode = self.settings.n8n_webhook_mode
        url_configured = bool(self.settings.n8n_webhook_url.strip())
        blockers = self._network_dispatch_blockers(
            mode=mode,
            url_configured=url_configured,
            requires_human_approval=self.settings.n8n_webhook_requires_human_approval,
        )
        return WebhookDispatchPolicy(
            mode=mode,
            url_configured=url_configured,
            timeout_seconds=self.settings.n8n_webhook_timeout_seconds,
            max_retries=self.settings.n8n_webhook_max_retries,
            requires_human_approval=self.settings.n8n_webhook_requires_human_approval,
            network_dispatch_allowed=not blockers,
            network_dispatch_blockers=tuple(blockers),
        )

    async def _dispatch_live(
        self,
        *,
        payload_summary: dict[str, object],
        policy: WebhookDispatchPolicy,
    ) -> WebhookDispatch:
        url = self.settings.n8n_webhook_url.strip()
        max_attempts = policy.max_retries + 1
        last_status_code = None
        last_error_type = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.http_client.post_json(
                    url=url,
                    payload=payload_summary,
                    timeout_seconds=policy.timeout_seconds,
                )
            except Exception as exc:
                last_error_type = type(exc).__name__
                if attempt == max_attempts:
                    return WebhookDispatch(
                        action_name="notify_n8n_webhook",
                        status="failed",
                        reason="n8n webhook dispatch failed before a successful response.",
                        payload_summary=payload_summary,
                        dispatch_policy=policy,
                        attempts=attempt,
                        response_status_code=last_status_code,
                        error_type=last_error_type,
                    )
                continue

            last_status_code = response.status_code
            last_error_type = None
            if 200 <= response.status_code < 300:
                return WebhookDispatch(
                    action_name="notify_n8n_webhook",
                    status="completed",
                    reason="n8n webhook notification sent successfully.",
                    payload_summary=payload_summary,
                    dispatch_policy=policy,
                    attempts=attempt,
                    response_status_code=response.status_code,
                )

            if attempt == max_attempts:
                return WebhookDispatch(
                    action_name="notify_n8n_webhook",
                    status="failed",
                    reason="n8n webhook dispatch returned a non-success status code.",
                    payload_summary=payload_summary,
                    dispatch_policy=policy,
                    attempts=attempt,
                    response_status_code=response.status_code,
                    error_type="HttpStatusError",
                )

        return WebhookDispatch(
            action_name="notify_n8n_webhook",
            status="failed",
            reason="n8n webhook dispatch failed.",
            payload_summary=payload_summary,
            dispatch_policy=policy,
            attempts=max_attempts,
            response_status_code=last_status_code,
            error_type=last_error_type,
        )

    def _blocked_status(self, policy: WebhookDispatchPolicy) -> str:
        if policy.mode == "disabled":
            return "simulated"
        if policy.mode == "simulated":
            return "simulated"
        if "human_approval_required" in policy.network_dispatch_blockers:
            return "human_approval_required"
        return "failed"

    def _blocked_reason(self, policy: WebhookDispatchPolicy) -> str:
        if policy.mode == "disabled":
            return "n8n webhook notification disabled; no external request was sent."
        if policy.mode == "simulated":
            return "n8n webhook notification simulated locally; no external request was sent."
        if "human_approval_required" in policy.network_dispatch_blockers:
            return "n8n webhook dispatch requires human approval; no external request was sent."
        return "n8n webhook dispatch is not configured; no external request was sent."

    def _network_dispatch_blockers(
        self,
        *,
        mode: str,
        url_configured: bool,
        requires_human_approval: bool,
    ) -> list[str]:
        blockers = []
        if mode == "disabled":
            blockers.append("mode_disabled")
        elif mode == "simulated":
            blockers.append("mode_simulated")
        if not url_configured:
            blockers.append("missing_webhook_url")
        if requires_human_approval:
            blockers.append("human_approval_required")
        return blockers
