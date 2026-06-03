import json
from pathlib import Path

from scripts.run_eval import (
    HeuristicSemanticJudge,
    _build_markdown_report,
    _result_to_dict,
    build_semantic_judge,
    build_summary,
    evaluate_response,
    load_dataset,
    load_document_manifest,
    resolve_document_ids,
)


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
                "metadata_filter": {"file_extensions": [".txt"]},
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
    assert cases[0].expected_answer_contains_any == []
    assert cases[0].expected_source_titles == ["policy.txt"]
    assert cases[0].metadata_filter == {"file_extensions": [".txt"]}


def test_committed_initial_dataset_is_well_formed() -> None:
    cases = load_dataset(Path("evals/initial_rag.jsonl"))
    case_ids = [case.id for case in cases]
    corpus_dir = Path("evals/corpus")

    assert len(cases) >= 30
    assert len(case_ids) == len(set(case_ids))
    for case in cases:
        assert case.question
        assert case.expected_status in {"generated", "insufficient_context", None}
        assert all(group for group in case.expected_answer_contains_any)
        assert set(case.metadata_filter).issubset({"document_ids", "file_extensions"})
        if case.expected_status == "generated":
            assert case.expected_source_titles
            for source_title in case.expected_source_titles:
                assert (corpus_dir / source_title).exists()


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
    assert result.failure_reasons == []
    assert result.actual_source_titles == ["policy.txt"]


def test_evaluate_response_accepts_answer_variant_groups() -> None:
    case = load_dataset_case(
        expected_answer_contains=[],
        expected_answer_contains_any=[["30 days", "thirty days"]],
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "The refund window is thirty days.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
    )

    assert result.passed is True


def test_evaluate_response_normalizes_answer_text_before_matching() -> None:
    case = load_dataset_case(
        expected_answer_contains=[],
        expected_answer_contains_any=[
            ["self serve subscriptions"],
            ["dont need to return"],
            ["gift card"],
        ],
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "Self-serve subscriptions don\u2019t need to return a gift-card receipt.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
    )

    assert result.passed is True


def test_evaluate_response_checks_fallback_quality() -> None:
    case = load_dataset_case(
        expected_status="insufficient_context",
        expected_answer_contains=[],
        expected_answer_contains_any=[],
        expected_source_titles=[],
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "There is not enough context to answer.",
            "retrieval_status": "insufficient_context",
            "sources": [],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
    )

    assert result.passed is False
    assert result.quality_passed is False
    assert result.quality_score == 0.75
    assert result.failure_reasons == ["quality"]
    assert result.quality_failure_reasons == ["fallback_behavior"]


def test_evaluate_response_checks_forbidden_terms_and_answer_length() -> None:
    case = load_dataset_case(
        expected_answer_contains=[],
        expected_answer_contains_any=[["30 days"]],
        forbidden_answer_contains=["guaranteed"],
        max_answer_chars=40,
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "Refunds are guaranteed and available within 30 days.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
    )

    assert result.passed is False
    assert result.answer_passed is True
    assert result.quality_passed is False
    assert result.quality_score == 0.5
    assert result.quality_failure_reasons == ["forbidden_terms", "answer_length"]


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
    assert summary["quality_passed"] == 2
    assert summary["average_quality_score"] == 1
    assert summary["semantic_evaluated"] == 0
    assert summary["semantic_passed"] == 0
    assert summary["average_semantic_score"] == 0
    assert summary["average_latency_ms"] == 20
    assert summary["estimated_cost_usd"] == 0.0003


def test_failed_result_records_expected_actual_and_reasons() -> None:
    case = load_dataset_case(
        expected_status="generated",
        expected_answer_contains=["30 days"],
        expected_source_titles=["policy.txt"],
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "No answer.",
            "retrieval_status": "no_results",
            "sources": [{"title": "other.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
    )

    payload = _result_to_dict(result)

    assert result.passed is False
    assert result.failure_reasons == ["retrieval_status", "answer", "sources"]
    assert payload["expected"]["retrieval_status"] == "generated"
    assert payload["expected"]["answer_contains"] == ["30 days"]
    assert payload["expected"]["forbidden_answer_contains"] == []
    assert payload["expected"]["max_answer_chars"] is None
    assert payload["actual"]["retrieval_status"] == "no_results"
    assert payload["actual"]["answer"] == "No answer."
    assert payload["actual"]["source_titles"] == ["other.txt"]
    assert payload["answer_correctness_passed"] is False
    assert payload["quality_passed"] is True
    assert payload["quality_score"] == 1
    assert payload["semantic"] == {
        "evaluated": False,
        "passed": True,
        "score": None,
        "threshold": None,
        "provider": "disabled",
        "rationale": "Semantic judge disabled.",
        "failure_reasons": [],
    }


def test_markdown_report_includes_failure_details() -> None:
    case = load_dataset_case(expected_answer_contains=["30 days"])
    result = evaluate_response(
        case=case,
        response={
            "answer": "No answer.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
    )

    markdown = _build_markdown_report(
        summary=build_summary([result]),
        results=[result],
    )

    assert "- Failure reasons: answer" in markdown
    assert "- Expected answer contains: ['30 days']" in markdown
    assert "- Actual answer: No answer." in markdown


def test_evaluate_response_runs_heuristic_semantic_judge() -> None:
    case = load_dataset_case(
        expected_answer_contains=[],
        expected_answer_contains_any=[
            ["customer may request refund within 30 days"],
        ],
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "A customer can ask for a refund in 30 days.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
        semantic_judge=HeuristicSemanticJudge(threshold=0.6),
    )

    assert result.passed is True
    assert result.answer_passed is False
    assert result.answer_correctness_passed is True
    assert result.semantic_evaluated is True
    assert result.semantic_passed is True
    assert result.semantic_score == 0.6667
    assert result.semantic_threshold == 0.6
    assert result.semantic_provider == "heuristic"
    assert result.failure_reasons == []


def test_semantic_judge_failure_adds_reason() -> None:
    case = load_dataset_case(
        expected_answer_contains=[],
        expected_answer_contains_any=[
            ["customer may request refund within 30 days"],
        ],
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "Customers receive store credit after approval.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
        semantic_judge=HeuristicSemanticJudge(threshold=0.8),
    )

    assert result.passed is False
    assert result.answer_passed is False
    assert result.answer_correctness_passed is False
    assert result.semantic_evaluated is True
    assert result.semantic_passed is False
    assert result.semantic_failure_reasons == ["expected_facts_below_threshold"]
    assert result.failure_reasons == ["semantic"]


def test_semantic_judge_skips_fallback_cases() -> None:
    case = load_dataset_case(
        expected_status="insufficient_context",
        expected_answer_contains=[],
        expected_answer_contains_any=[],
        expected_source_titles=[],
    )

    result = evaluate_response(
        case=case,
        response={
            "answer": "I do not have enough context to answer.",
            "retrieval_status": "insufficient_context",
            "sources": [],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=12.5,
        semantic_judge=HeuristicSemanticJudge(threshold=0.8),
    )

    assert result.semantic_evaluated is False
    assert result.semantic_passed is True
    assert result.semantic_score is None
    assert result.semantic_rationale == "Case expects fallback behavior."


def test_build_summary_reports_semantic_metrics() -> None:
    passing_case = load_dataset_case(
        expected_answer_contains=[],
        expected_answer_contains_any=[["refund within 30 days"]],
    )
    skipped_case = load_dataset_case(
        expected_status="insufficient_context",
        expected_answer_contains=[],
        expected_answer_contains_any=[],
        expected_source_titles=[],
    )
    judge = HeuristicSemanticJudge(threshold=0.8)
    passing_result = evaluate_response(
        case=passing_case,
        response={
            "answer": "A refund is available within 30 days.",
            "retrieval_status": "generated",
            "sources": [{"title": "policy.txt"}],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=10,
        semantic_judge=judge,
    )
    skipped_result = evaluate_response(
        case=skipped_case,
        response={
            "answer": "I do not have enough context to answer.",
            "retrieval_status": "insufficient_context",
            "sources": [],
            "usage": {"estimated_cost_usd": 0.0001},
        },
        latency_ms=20,
        semantic_judge=judge,
    )

    summary = build_summary([passing_result, skipped_result])

    assert summary["semantic_evaluated"] == 1
    assert summary["semantic_passed"] == 1
    assert summary["average_semantic_score"] == 1


def test_build_semantic_judge_validates_threshold() -> None:
    judge = build_semantic_judge(provider="heuristic", threshold=0.7)

    assert isinstance(judge, HeuristicSemanticJudge)

    try:
        build_semantic_judge(provider="heuristic", threshold=1.5)
    except RuntimeError as exc:
        assert "--semantic-threshold" in str(exc)
    else:
        raise AssertionError("Expected invalid semantic threshold to fail.")


def test_load_document_manifest_maps_titles_to_document_ids(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "documents": [
                    {"title": "refund_policy.txt", "document_id": "doc-refund"},
                    {"title": "billing_policy.txt", "document_id": "doc-billing"},
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = load_document_manifest(manifest_path)

    assert manifest == {
        "refund_policy.txt": "doc-refund",
        "billing_policy.txt": "doc-billing",
    }


def test_resolve_document_ids_prefers_explicit_override() -> None:
    case = load_dataset_case(expected_source_titles=["refund_policy.txt"])

    document_ids = resolve_document_ids(
        case=case,
        document_id="override-doc",
        manifest_document_ids={"refund_policy.txt": "manifest-doc"},
    )

    assert document_ids == ["override-doc"]


def test_resolve_document_ids_uses_manifest_titles() -> None:
    case = load_dataset_case(expected_source_titles=["refund_policy.txt"])

    document_ids = resolve_document_ids(
        case=case,
        document_id=None,
        manifest_document_ids={"refund_policy.txt": "manifest-doc"},
    )

    assert document_ids == ["manifest-doc"]


def load_dataset_case(
    expected_status: str = "generated",
    expected_answer_contains: list[str] | None = None,
    expected_answer_contains_any: list[list[str]] | None = None,
    forbidden_answer_contains: list[str] | None = None,
    max_answer_chars: int | None = None,
    expected_source_titles: list[str] | None = None,
):
    dataset = {
        "id": "case-1",
        "question": "What is the refund window?",
        "expected_status": expected_status,
        "expected_answer_contains": (
            ["30 days"] if expected_answer_contains is None else expected_answer_contains
        ),
        "expected_answer_contains_any": expected_answer_contains_any or [],
        "forbidden_answer_contains": forbidden_answer_contains or [],
        "max_answer_chars": max_answer_chars,
        "expected_source_titles": (
            ["policy.txt"] if expected_source_titles is None else expected_source_titles
        ),
        "metadata_filter": {},
    }
    from scripts.run_eval import _case_from_payload

    return _case_from_payload(dataset, line_number=1)
