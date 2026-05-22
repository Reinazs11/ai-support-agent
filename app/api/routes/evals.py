from fastapi import APIRouter

from app.evals.schemas import EvaluationRunRequest, EvaluationRunResponse
from app.evals.service import EvaluationService

router = APIRouter()


@router.post("/evals/run", response_model=EvaluationRunResponse)
async def run_evaluation(request: EvaluationRunRequest) -> EvaluationRunResponse:
    return EvaluationService().run(request)
