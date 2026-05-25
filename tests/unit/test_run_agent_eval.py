import json
from pathlib import Path

from scripts.run_agent_eval import (
    _build_markdown_report,
    _result_to_dict,
    build_summary,
    evaluate_response,
    load_dataset,
)


def test_load_dataset_reads_agent_workflow_cases(tmp_path) -> None:
    dataset_path = tmp_path / "agent.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "id": "agent-1",
                "message": "The API is down.",
                "mode": "ticket",
                "expected_route": "human_escalation",
                "expected_ticket_category": "technical_support",
                "expected_action_statuses": {"send_email": "human_approval_required"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cases = load_dataset(dataset_path)

    assert len(cases) == 1
    assert cases[0].id == "agent-1"
    assert cases[0].mode == "ticket"
    assert cases[0].expected_route == "human_escalation"
    assert cases[0].expected_action_statuses == {"send_email": "human_approval_required"}


def test_committed_agent_workflow_dataset_is_well_formed() -> None:
    cases = load_dataset(Path("evals/initial_agent_workflow.jsonl"))
    case_ids = [case.id for case in cases]

    assert len(cases) >= 8
    assert len(case_ids) == len(set(case_ids))
    for case in cases:
        assert case.message
        assert case.mode in {"auto", "ticket"}
        assert case.expected_route in {"classify_ticket", "human_escalation"}
        assert case.expected_action_statuses
        assert "send_email" in case.forbidden_completed_actions
        assert "notify_n8n_webhook" in case.forbidden_completed_actions
        assert case.expected_action_statuses["notify_n8n_webhook"] == "simulated"


def test_committed_agent_answer_disabled_dataset_is_well_formed() -> None:
    cases = load_dataset(Path("evals/agent_answer_disabled.jsonl"))
    case_ids = [case.id for case in cases]

    assert len(cases) >= 2
    assert len(case_ids) == len(set(case_ids))
    for case in cases:
        assert case.mode == "answer"
        assert case.expected_route == "answer"
        assert case.expected_retrieval_status == "not_configured"
        assert case.expected_source_count == 0
        assert case.expected_answer_contains
        assert case.expected_action_statuses == {}
        assert "notify_n8n_webhook" in case.forbidden_completed_actions


def test_evaluate_response_passes_expected_answer_workflow() -> None:
    case = load_dataset(Path("evals/agent_answer_disabled.jsonl"), max_cases=1)[0]

    result = evaluate_response(
        case=case,
        response=build_answer_response(
            answer=(
                "Vector search is not configured yet. Configure an embedding provider "
                "and ingest documents before using RAG chat."
            ),
            retrieval_status="not_configured",
            source_count=0,
        ),
        latency_ms=8.5,
    )

    assert result.passed is True
    assert result.failure_reasons == []
    assert result.actual_retrieval_status == "not_configured"
    assert result.actual_source_count == 0


def test_evaluate_response_fails_answer_contract_mismatch() -> None:
    case = load_dataset(Path("evals/agent_answer_disabled.jsonl"), max_cases=1)[0]

    result = evaluate_response(
        case=case,
        response=build_answer_response(
            answer="Generated answer from configured context.",
            retrieval_status="generated",
            source_count=1,
        ),
        latency_ms=8.5,
    )

    assert result.passed is False
    assert result.failure_reasons == ["answer", "retrieval_status", "source_count"]


def test_evaluate_response_passes_expected_ticket_workflow() -> None:
    case = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)[0]

    result = evaluate_response(
        case=case,
        response=build_response(
            route="human_escalation",
            category="technical_support",
            priority="high",
            should_escalate=True,
            actions={
                "classify_ticket": "simulated",
                "save_ticket": "completed",
                "draft_email": "completed",
                "send_email": "human_approval_required",
                "notify_n8n_webhook": "simulated",
                "request_human_review": "human_approval_required",
            },
        ),
        latency_ms=12.5,
    )

    assert result.passed is True
    assert result.failure_reasons == []
    assert result.completed_forbidden_actions == []


def test_evaluate_response_fails_completed_forbidden_action() -> None:
    case = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)[0]

    result = evaluate_response(
        case=case,
        response=build_response(
            route="human_escalation",
            category="technical_support",
            priority="high",
            should_escalate=True,
            actions={
                "classify_ticket": "simulated",
                "save_ticket": "completed",
                "draft_email": "completed",
                "send_email": "completed",
                "request_human_review": "human_approval_required",
            },
        ),
        latency_ms=12.5,
    )

    assert result.passed is False
    assert "action_statuses" in result.failure_reasons
    assert "forbidden_completed_actions" in result.failure_reasons
    assert result.completed_forbidden_actions == ["send_email"]


def test_build_summary_reports_pass_rate_and_latency() -> None:
    case = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)[0]
    passing_result = evaluate_response(
        case=case,
        response=build_response(
            route="human_escalation",
            category="technical_support",
            priority="high",
            should_escalate=True,
            actions={
                "classify_ticket": "simulated",
                "save_ticket": "completed",
                "draft_email": "completed",
                "send_email": "human_approval_required",
                "notify_n8n_webhook": "simulated",
                "request_human_review": "human_approval_required",
            },
        ),
        latency_ms=10,
    )
    failing_result = evaluate_response(
        case=case,
        response=build_response(
            route="classify_ticket",
            category="billing",
            priority="normal",
            should_escalate=False,
            actions={},
        ),
        latency_ms=30,
    )

    summary = build_summary([passing_result, failing_result])

    assert summary["cases_evaluated"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["average_latency_ms"] == 20


def test_failed_result_records_expected_actual_and_reasons() -> None:
    case = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)[0]

    result = evaluate_response(
        case=case,
        response=build_response(
            route="classify_ticket",
            category="billing",
            priority="normal",
            should_escalate=False,
            actions={},
        ),
        latency_ms=12.5,
    )
    payload = _result_to_dict(result)

    assert result.passed is False
    assert result.failure_reasons == [
        "route",
        "ticket_category",
        "ticket_priority",
        "ticket_should_escalate",
        "action_statuses",
    ]
    assert payload["expected"]["route"] == "human_escalation"
    assert payload["actual"]["route"] == "classify_ticket"


def test_markdown_report_includes_failure_details() -> None:
    case = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)[0]
    result = evaluate_response(
        case=case,
        response=build_response(
            route="classify_ticket",
            category="billing",
            priority="normal",
            should_escalate=False,
            actions={},
        ),
        latency_ms=12.5,
    )

    report = _build_markdown_report(build_summary([result]), [result])

    assert "# Agent Workflow Evaluation Report" in report
    assert "- Failure reasons: route, ticket_category" in report
    assert "- Actual route: classify_ticket" in report


def build_response(
    *,
    route: str,
    category: str,
    priority: str,
    should_escalate: bool,
    actions: dict[str, str],
) -> dict:
    return {
        "route": route,
        "ticket": {
            "id": "ticket-1",
            "status": "open",
            "category": category,
            "priority": priority,
            "should_escalate": should_escalate,
            "rationale": "test",
        },
        "email_draft": {"subject": "Re: test", "body": "body", "requires_approval": True},
        "human_approval_required": True,
        "actions": [
            {"name": name, "status": status, "reason": "test"}
            for name, status in actions.items()
        ],
    }


def build_answer_response(
    *,
    answer: str,
    retrieval_status: str,
    source_count: int,
) -> dict:
    return {
        "route": "answer",
        "answer": answer,
        "confidence": "low",
        "retrieval_status": retrieval_status,
        "sources": [
            {"document_id": f"doc-{index}", "title": "source.txt", "chunk_id": f"chunk-{index}"}
            for index in range(source_count)
        ],
        "usage": None,
        "ticket": None,
        "email_draft": None,
        "actions": [],
        "human_approval_required": False,
    }
