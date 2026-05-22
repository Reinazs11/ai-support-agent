from pydantic import BaseModel, Field


class EvaluationRunRequest(BaseModel):
    dataset_path: str = "evals/questions.yaml"
    max_questions: int | None = Field(default=None, ge=1)


class EvaluationRunResponse(BaseModel):
    status: str
    dataset_path: str
    questions_evaluated: int = 0
    report_path: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
