from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    environment: str
    dependencies: dict[str, str] = Field(default_factory=dict)
