from fastapi import APIRouter, HTTPException

from app.evals.schemas import EvaluationRunRequest

router = APIRouter()


@router.post("/evals/run")
async def run_evaluation(request: EvaluationRunRequest) -> None:
    raise HTTPException(
        status_code=501,
        detail=(
            "API-triggered evaluation runs are not implemented. "
            "Use `python -m scripts.run_eval` for the current controlled local flow."
        ),
    )
