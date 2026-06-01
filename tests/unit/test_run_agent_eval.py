import json
from pathlib import Path

from scripts.run_agent_eval import (
    _build_markdown_report,
    _requires_health_preflight,
    _result_to_dict,
    build_summary,
    evaluate_response,
    load_dataset,
    load_document_manifest,
    resolve_document_ids,
    validate_agent_eval_environment,
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
                "requires_agent_router_provider": "llm",
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
    assert cases[0].requires_agent_router_provider == "llm"


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


def test_committed_agent_answer_seeded_dataset_is_well_formed() -> None:
    cases = load_dataset(Path("evals/agent_answer_seeded.jsonl"))
    case_ids = [case.id for case in cases]

    assert len(cases) >= 3
    assert len(case_ids) == len(set(case_ids))
    for case in cases:
        assert case.mode == "answer"
        assert case.expected_route == "answer"
        assert case.expected_answer_contains
        assert case.expected_action_statuses == {}
        assert case.forbidden_completed_actions
        if case.expected_retrieval_status == "generated":
            assert case.expected_source_titles
            assert case.expected_min_source_count == 1


def test_committed_agent_router_llm_dataset_is_well_formed() -> None:
    cases = load_dataset(Path("evals/agent_router_llm.jsonl"))
    case_ids = [case.id for case in cases]

    assert len(cases) >= 3
    assert len(case_ids) == len(set(case_ids))
    for case in cases:
        assert case.mode == "auto"
        assert case.requires_agent_router_provider == "llm"
        assert case.expected_route in {"answer", "classify_ticket"}
        assert "send_email" in case.forbidden_completed_actions
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


def test_evaluate_response_passes_expected_seeded_answer_workflow() -> None:
    case = load_dataset(Path("evals/agent_answer_seeded.jsonl"), max_cases=1)[0]

    result = evaluate_response(
        case=case,
        response=build_answer_response(
            answer="Self-serve subscription refunds are available within 30 days.",
            retrieval_status="generated",
            source_titles=["refund_policy.txt"],
        ),
        latency_ms=8.5,
    )

    assert result.passed is True
    assert result.failure_reasons == []
    assert result.actual_source_titles == ["refund_policy.txt"]


def test_evaluate_response_fails_answer_contract_mismatch() -> None:
    case = load_dataset(Path("evals/agent_answer_disabled.jsonl"), max_cases=1)[0]

    result = evaluate_response(
        case=case,
        response=build_answer_response(
            answer="Generated answer from configured context.",
            retrieval_status="generated",
            source_titles=["source.txt"],
        ),
        latency_ms=8.5,
    )

    assert result.passed is False
    assert result.failure_reasons == ["answer", "retrieval_status", "source_count"]


def test_evaluate_response_fails_seeded_answer_source_mismatch() -> None:
    case = load_dataset(Path("evals/agent_answer_seeded.jsonl"), max_cases=1)[0]

    result = evaluate_response(
        case=case,
        response=build_answer_response(
            answer="Self-serve subscription refunds are available within 30 days.",
            retrieval_status="generated",
            source_titles=["billing_policy.txt"],
        ),
        latency_ms=8.5,
    )

    assert result.passed is False
    assert result.failure_reasons == ["source_titles"]


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
            router_usage={
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "estimated_cost_usd": 0.000045,
            },
        ),
        latency_ms=12.5,
    )

    assert result.passed is True
    assert result.failure_reasons == []
    assert result.completed_forbidden_actions == []
    assert result.actual_router_provider == "openai"
    assert result.actual_router_model == "gpt-test"
    assert result.actual_router_prompt_tokens == 100
    assert result.actual_router_completion_tokens == 20
    assert result.actual_router_total_tokens == 120
    assert result.actual_router_estimated_cost_usd == 0.000045


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
    assert summary["router_prompt_tokens"] == 0
    assert summary["router_completion_tokens"] == 0
    assert summary["router_total_tokens"] == 0
    assert summary["router_estimated_cost_usd"] is None


def test_build_summary_reports_router_usage_and_cost() -> None:
    case = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)[0]
    first_result = evaluate_response(
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
            router_usage={
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "estimated_cost_usd": 0.000045,
            },
        ),
        latency_ms=10,
    )
    second_result = evaluate_response(
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
            router_usage={
                "prompt_tokens": 110,
                "completion_tokens": 30,
                "total_tokens": 140,
                "estimated_cost_usd": 0.00006,
            },
        ),
        latency_ms=20,
    )

    summary = build_summary([first_result, second_result])

    assert summary["router_prompt_tokens"] == 210
    assert summary["router_completion_tokens"] == 50
    assert summary["router_total_tokens"] == 260
    assert summary["router_estimated_cost_usd"] == 0.000105


def test_validate_agent_eval_environment_accepts_matching_router_provider() -> None:
    case = load_dataset(Path("evals/agent_router_llm.jsonl"), max_cases=1)[0]

    validate_agent_eval_environment(
        cases=[case],
        dependencies={"agent_router": "llm"},
    )


def test_validate_agent_eval_environment_rejects_wrong_router_provider() -> None:
    case = load_dataset(Path("evals/agent_router_llm.jsonl"), max_cases=1)[0]

    try:
        validate_agent_eval_environment(
            cases=[case],
            dependencies={"agent_router": "deterministic"},
        )
    except RuntimeError as exc:
        assert "requires agent_router=llm" in str(exc)
        assert "agent_router=deterministic" in str(exc)
    else:
        raise AssertionError("Expected router provider mismatch to fail.")


def test_validate_agent_eval_environment_rejects_live_n8n_for_simulated_dataset() -> None:
    case = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)[0]

    try:
        validate_agent_eval_environment(
            cases=[case],
            dependencies={"n8n": "live", "agent_router": "deterministic"},
        )
    except RuntimeError as exc:
        assert "expects notify_n8n_webhook=simulated" in str(exc)
        assert "n8n=live" in str(exc)
        assert "N8N_WEBHOOK_MODE=simulated" in str(exc)
    else:
        raise AssertionError("Expected live n8n guard to fail.")


def test_validate_agent_eval_environment_accepts_simulated_n8n_for_simulated_dataset() -> None:
    case = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)[0]

    validate_agent_eval_environment(
        cases=[case],
        dependencies={"n8n": "simulated", "agent_router": "deterministic"},
    )


def test_default_agent_eval_dataset_requires_health_preflight() -> None:
    cases = load_dataset(Path("evals/initial_agent_workflow.jsonl"), max_cases=1)

    assert _requires_health_preflight(cases) is True


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
    assert "router_total_tokens" in payload["actual"]


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
    assert "- Router total tokens: 0" in report


def test_load_document_manifest_maps_titles_to_document_ids(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "documents": [
                    {"title": "refund_policy.txt", "document_id": "refund-doc"},
                    {"title": "support_sla.txt", "document_id": "sla-doc"},
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = load_document_manifest(manifest_path)

    assert manifest == {
        "refund_policy.txt": "refund-doc",
        "support_sla.txt": "sla-doc",
    }


def test_resolve_document_ids_prefers_explicit_override() -> None:
    case = load_dataset(Path("evals/agent_answer_seeded.jsonl"), max_cases=1)[0]

    document_ids = resolve_document_ids(
        case=case,
        document_id="override-doc",
        manifest_document_ids={"refund_policy.txt": "manifest-doc"},
    )

    assert document_ids == ["override-doc"]


def test_resolve_document_ids_uses_case_document_ids() -> None:
    dataset_case = load_dataset_case(document_ids=["case-doc"])

    document_ids = resolve_document_ids(
        case=dataset_case,
        document_id=None,
        manifest_document_ids={"refund_policy.txt": "manifest-doc"},
    )

    assert document_ids == ["case-doc"]


def test_resolve_document_ids_uses_manifest_source_titles() -> None:
    case = load_dataset(Path("evals/agent_answer_seeded.jsonl"), max_cases=1)[0]

    document_ids = resolve_document_ids(
        case=case,
        document_id=None,
        manifest_document_ids={"refund_policy.txt": "manifest-doc"},
    )

    assert document_ids == ["manifest-doc"]


def test_resolve_document_ids_requires_manifest_titles() -> None:
    case = load_dataset(Path("evals/agent_answer_seeded.jsonl"), max_cases=1)[0]

    try:
        resolve_document_ids(
            case=case,
            document_id=None,
            manifest_document_ids={"billing_policy.txt": "billing-doc"},
        )
    except RuntimeError as exc:
        assert "refund_policy.txt" in str(exc)
    else:
        raise AssertionError("Expected missing manifest title to fail.")


def build_response(
    *,
    route: str,
    category: str,
    priority: str,
    should_escalate: bool,
    actions: dict[str, str],
    router_usage: dict | None = None,
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
        "router": {
            "provider": "openai",
            "model": "gpt-test",
            "fallback_reason": None,
            "latency_ms": 12.3,
            "usage": router_usage,
        },
    }


def build_answer_response(
    *,
    answer: str,
    retrieval_status: str,
    source_count: int | None = None,
    source_titles: list[str] | None = None,
) -> dict:
    titles = source_titles or [
        "source.txt"
        for _ in range(source_count or 0)
    ]
    return {
        "route": "answer",
        "answer": answer,
        "confidence": "low",
        "retrieval_status": retrieval_status,
        "sources": [
            {"document_id": f"doc-{index}", "title": title, "chunk_id": f"chunk-{index}"}
            for index, title in enumerate(titles)
        ],
        "usage": None,
        "ticket": None,
        "email_draft": None,
        "actions": [],
        "human_approval_required": False,
    }


def load_dataset_case(
    *,
    document_ids: list[str] | None = None,
):
    dataset_path = Path("evals/agent_answer_seeded.jsonl")
    case = load_dataset(dataset_path, max_cases=1)[0]
    return type(case)(
        id=case.id,
        message=case.message,
        mode=case.mode,
        document_ids=document_ids or [],
        top_k=case.top_k,
        expected_answer_contains=case.expected_answer_contains,
        expected_retrieval_status=case.expected_retrieval_status,
        expected_source_count=case.expected_source_count,
        expected_min_source_count=case.expected_min_source_count,
        expected_source_titles=case.expected_source_titles,
        expected_route=case.expected_route,
        expected_ticket_category=case.expected_ticket_category,
        expected_ticket_priority=case.expected_ticket_priority,
        expected_ticket_should_escalate=case.expected_ticket_should_escalate,
        expected_human_approval_required=case.expected_human_approval_required,
        expected_email_draft_present=case.expected_email_draft_present,
        expected_action_statuses=case.expected_action_statuses,
        forbidden_completed_actions=case.forbidden_completed_actions,
        requires_agent_router_provider=case.requires_agent_router_provider,
    )
