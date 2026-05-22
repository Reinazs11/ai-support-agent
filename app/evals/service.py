from app.evals.schemas import EvaluationRunRequest, EvaluationRunResponse


class EvaluationService:
    def run(self, request: EvaluationRunRequest) -> EvaluationRunResponse:
        return EvaluationRunResponse(
            status="pending_dataset",
            dataset_path=request.dataset_path,
            questions_evaluated=0,
            report_path=None,
            metrics={},
        )
