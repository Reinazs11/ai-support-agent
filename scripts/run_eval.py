from app.evals.schemas import EvaluationRunRequest
from app.evals.service import EvaluationService


def main() -> None:
    result = EvaluationService().run(EvaluationRunRequest())
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
