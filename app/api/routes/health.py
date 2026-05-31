from fastapi import APIRouter

from app.core.config import get_settings
from app.core.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    settings = get_settings()
    openai_configured = bool(
        settings.openai_api_key or settings.embedding_api_key or settings.chat_api_key
    )
    n8n_status = settings.n8n_webhook_mode
    if settings.n8n_webhook_mode == "live":
        if not settings.n8n_webhook_url.strip():
            n8n_status = "missing_webhook_url"
        elif settings.n8n_webhook_requires_human_approval:
            n8n_status = "human_approval_required"
    agent_router_status = settings.agent_router_provider
    if settings.agent_router_provider == "llm":
        if settings.chat_provider != "openai":
            agent_router_status = "llm_chat_provider_disabled"
        elif not (settings.chat_api_key or settings.openai_api_key):
            agent_router_status = "llm_missing_api_key"
    langfuse_status = "disabled"
    if settings.langfuse_enabled:
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            langfuse_status = "configured"
        else:
            langfuse_status = "missing_credentials"
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.app_env,
        dependencies={
            "postgres": "configured",
            "qdrant": "configured",
            "openai": "configured" if openai_configured else "missing_api_key",
            "n8n": n8n_status,
            "agent_router": agent_router_status,
            "langfuse": langfuse_status,
        },
    )
