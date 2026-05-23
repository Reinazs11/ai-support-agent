import json

from scripts.run_eval import build_summary, evaluate_response, load_dataset


def test_load_dataset_reads_jsonl_cases(tmp_path) -> None:
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "id": "case-1",
                "question": "What is the refund window?",
                "expected_status": "generated",
                "expected_answer_contains": ["30 days"],
                "expected_source_titles": ["policy.txt"],
                "top_k": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cases = load_dataset(dataset_path)

    assert len(cases) == 1
    assert cases[0].id == "case-1"
    assert cases[0].expected_answer_contains == ["30 days"]
    assert cases[0].expected_source_titles == ["policy.txt"]


def test_evaluate_response_checks_status_answer_and_source() -> None:
    case = load_dataset_case(
        expected_status="generated",
        expected_answer_contains=["30 days"],
        expected_source_titles=["policy.txt"],
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "Refunds are available within 30 days.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
    )

    assert result.passed is True
    assert result.estimated_cost_usd == 0.0001


def test_build_summary_reports_pass_rate_latency_and_cost() -> None:
    case = load_dataset_case()
    passing_result = evaluate_response(
        case=case,
        response={
            "answer": "Refunds are available within 30 days.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=10,
    )
    failing_result = evaluate_response(
        case=case,
        response={
            "answer": "No answer.",
            "retrieval_status": "no_results",
            "sources": [],
            "usage": {"estimated_cost_usd": 0.0002},
        },
        latency_ms=30,
    )

    summary = build_summary([passing_result, failing_result])

    assert summary["questions_evaluated"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["average_latency_ms"] == 20
    assert summary["estimated_cost_usd"] == 0.0003


def load_dataset_case(
    expected_status: str = "generated",
    expected_answer_contains: list[str] | None = None,
    expected_source_titles: list[str] | None = None,
):
    dataset = {
        "id": "case-1",
        "question": "What is the refund window?",
        "expected_status": expected_status,
        "expected_answer_contains": expected_answer_contains or ["30 days"],
        "expected_source_titles": expected_source_titles or ["policy.txt"],
    }
    from scripts.run_eval import _case_from_payload

    return _case_from_payload(dataset, line_number=1)
