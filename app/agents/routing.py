import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

if TYPE_CHECKING:
    from app.core.config import Settings

AgentWorkflowRoute = Literal["answer", "classify_ticket"]
AgentRequestMode = Literal["auto", "answer", "ticket"]

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


class AgentRouterConfigurationError(ValueError):
    pass


class AgentRouterProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentRouteDecision:
    route: AgentWorkflowRoute
    provider: str
    rationale: str
    model: str | None = None
    fallback_reason: str | None = None


class AgentRouter(Protocol):
    async def route(self, message: str, mode: AgentRequestMode) -> AgentRouteDecision:
        pass


class AgentRouteModelService(Protocol):
    model: str

    async def classify_route(self, message: str) -> AgentRouteDecision:
        pass


class DeterministicAgentRouter:
    async def route(self, message: str, mode: AgentRequestMode) -> AgentRouteDecision:
        if mode == "answer":
            return AgentRouteDecision(
                route="answer",
                provider="deterministic",
                rationale="explicit_answer_mode",
            )
        if mode == "ticket":
            return AgentRouteDecision(
                route="classify_ticket",
                provider="deterministic",
                rationale="explicit_ticket_mode",
            )
        if looks_like_ticket(message):
            return AgentRouteDecision(
                route="classify_ticket",
                provider="deterministic",
                rationale="ticket_signal_terms",
            )
        return AgentRouteDecision(
            route="answer",
            provider="deterministic",
            rationale="no_ticket_signal_terms",
        )


class FallbackAgentRouter:
    def __init__(
        self,
        primary: AgentRouteModelService,
        fallback: AgentRouter | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback or DeterministicAgentRouter()

    async def route(self, message: str, mode: AgentRequestMode) -> AgentRouteDecision:
        if mode != "auto":
            return await self.fallback.route(message=message, mode=mode)

        try:
            return await self.primary.classify_route(message)
        except (AgentRouterConfigurationError, AgentRouterProviderError) as exc:
            fallback_decision = await self.fallback.route(message=message, mode=mode)
            return AgentRouteDecision(
                route=fallback_decision.route,
                provider=fallback_decision.provider,
                rationale=fallback_decision.rationale,
                model=self.primary.model,
                fallback_reason=type(exc).__name__,
            )


class UnconfiguredAgentRouteModelService:
    model = "unconfigured"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def classify_route(self, message: str) -> AgentRouteDecision:
        raise AgentRouterConfigurationError(self.reason)


class OpenAIAgentRouteModelService:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise AgentRouterConfigurationError("An API key is required for OpenAI routing.")
        if not model:
            raise AgentRouterConfigurationError("A model is required for OpenAI routing.")
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def classify_route(self, message: str) -> AgentRouteDecision:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=build_agent_route_messages(message),
                temperature=0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise AgentRouterProviderError("OpenAI route classification failed.") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise AgentRouterProviderError("OpenAI returned an empty route response.")

        return parse_agent_route_response(
            content=content,
            provider="openai",
            model=self.model,
        )


def build_agent_router(settings: "Settings") -> AgentRouter:
    if settings.agent_router_provider == "deterministic":
        return DeterministicAgentRouter()

    if settings.agent_router_provider == "llm":
        if settings.chat_provider != "openai":
            route_model: AgentRouteModelService = UnconfiguredAgentRouteModelService(
                "LLM routing requires CHAT_PROVIDER=openai."
            )
        else:
            api_key = settings.chat_api_key or settings.openai_api_key
            model = (
                settings.agent_router_model
                or settings.chat_model
                or settings.openai_chat_model
            )
            try:
                route_model = OpenAIAgentRouteModelService(api_key=api_key, model=model)
            except AgentRouterConfigurationError as exc:
                route_model = UnconfiguredAgentRouteModelService(str(exc))
        return FallbackAgentRouter(primary=route_model)

    raise AgentRouterConfigurationError(
        f"Unsupported agent router provider '{settings.agent_router_provider}'."
    )


def build_agent_route_messages(message: str) -> list[ChatCompletionMessageParam]:
    return [
        cast(
            ChatCompletionMessageParam,
            {
                "role": "system",
                "content": (
                    "Classify a support-agent request into exactly one route. "
                    "Use classify_ticket when the user is reporting an issue, "
                    "requesting support follow-up, asking for billing help, or "
                    "needs a ticket-like workflow. Use answer when the user is "
                    "asking a knowledge-base question that should be answered "
                    "from documents. Return only JSON with keys route and rationale. "
                    "route must be either answer or classify_ticket. Keep rationale "
                    "short and do not include private user details."
                ),
            },
        ),
        cast(
            ChatCompletionMessageParam,
            {
                "role": "user",
                "content": f"Request:\n{message}",
            },
        ),
    ]


def parse_agent_route_response(
    content: str,
    provider: str,
    model: str | None = None,
) -> AgentRouteDecision:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AgentRouterProviderError("Route response was not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise AgentRouterProviderError("Route response must be a JSON object.")

    route = parsed.get("route")
    if route not in {"answer", "classify_ticket"}:
        raise AgentRouterProviderError("Route response contained an unsupported route.")

    rationale = parsed.get("rationale", "")
    if not isinstance(rationale, str):
        rationale = ""

    return AgentRouteDecision(
        route=route,
        provider=provider,
        rationale=rationale.strip()[:240] or "llm_route_classification",
        model=model,
    )


def looks_like_ticket(message: str) -> bool:
    normalized = message.lower()
    return any(term in normalized for term in TICKET_SIGNAL_TERMS)
