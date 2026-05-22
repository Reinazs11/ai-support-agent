from fastapi import APIRouter

from app.core.config import get_settings
from app.core.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.app_env,
        dependencies={
            "postgres": "configured",
            "qdrant": "configured",
            "openai": "configured" if settings.openai_api_key else "missing_api_key",
        },
    )
