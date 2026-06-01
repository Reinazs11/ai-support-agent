import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx


@dataclass(frozen=True)
class AgentEvalCase:
    id: str
    message: str
    mode: str
    document_ids: list[str]
    top_k: int | None
    expected_answer_contains: list[str]
    expected_retrieval_status: str | None
    expected_source_count: int | None
    expected_min_source_count: int | None
    expected_source_titles: list[str]
    expected_route: str
    expected_ticket_category: str | None
    expected_ticket_priority: str | None
    expected_ticket_should_escalate: bool | None
    expected_human_approval_required: bool | None
    expected_email_draft_present: bool | None
    expected_action_statuses: dict[str, str]
    forbidden_completed_actions: list[str]
    requires_agent_router_provider: str | None


@dataclass(frozen=True)
class AgentEvalResult:
    case_id: str
    passed: bool
    failure_reasons: list[str]
    expected_route: str
    expected_answer_contains: list[str]
    expected_retrieval_status: str | None
    expected_source_count: int | None
    expected_min_source_count: int | None
    expected_source_titles: list[str]
    expected_ticket_category: str | None
    expected_ticket_priority: str | None
    expected_ticket_should_escalate: bool | None
    expected_human_approval_required: bool | None
    expected_email_draft_present: bool | None
    expected_action_statuses: dict[str, str]
    forbidden_completed_actions: list[str]
    requires_agent_router_provider: str | None
    actual_answer: str | None
    actual_retrieval_status: str | None
    actual_source_count: int
    actual_source_titles: list[str]
    actual_route: str | None
    actual_ticket_category: str | None
    actual_ticket_priority: str | None
    actual_ticket_should_escalate: bool | None
    actual_human_approval_required: bool | None
    actual_email_draft_present: bool
    actual_action_statuses: dict[str, str]
    completed_forbidden_actions: list[str]
    actual_router_provider: str | None
    actual_router_model: str | None
    actual_router_prompt_tokens: int | None
    actual_router_completion_tokens: int | None
    actual_router_total_tokens: int | None
    actual_router_estimated_cost_usd: float | None
    latency_ms: float
    response: dict[str, Any]


def load_dataset(path: Path, max_cases: int | None = None) -> list[AgentEvalCase]:
    cases: list[AgentEvalCase] = []
    with path.open(encoding="utf-8") as dataset_file:
        for line_number, line in enumerate(dataset_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            cases.append(_case_from_payload(payload=payload, line_number=line_number))
            if max_cases is not None and len(cases) >= max_cases:
                break
    return cases


def evaluate_response(
    *,
    case: AgentEvalCase,
    response: dict[str, Any],
    latency_ms: float,
) -> AgentEvalResult:
    ticket = response.get("ticket") or {}
    actual_action_statuses = _action_statuses(response)
    completed_forbidden_actions = [
        action_name
        for action_name in case.forbidden_completed_actions
        if actual_action_statuses.get(action_name) == "completed"
    ]
    answer = response.get("answer")
    answer_text = answer if isinstance(answer, str) else ""
    sources = response.get("sources") or []
    actual_source_titles = _source_titles(sources)
    router = response.get("router") if isinstance(response.get("router"), dict) else {}
    router_usage = (
        router.get("usage")
        if isinstance(router, dict) and isinstance(router.get("usage"), dict)
        else {}
    )

    route_passed = response.get("route") == case.expected_route
    answer_passed = all(
        expected.casefold() in answer_text.casefold()
        for expected in case.expected_answer_contains
    )
    retrieval_status_passed = _optional_equal(
        actual=response.get("retrieval_status"),
        expected=case.expected_retrieval_status,
    )
    source_count_passed = _optional_equal(
        actual=len(sources),
        expected=case.expected_source_count,
    )
    min_source_count_passed = (
        case.expected_min_source_count is None
        or len(sources) >= case.expected_min_source_count
    )
    source_titles_passed = all(
        expected_title in actual_source_titles
        for expected_title in case.expected_source_titles
    )
    ticket_category_passed = _optional_equal(
        actual=ticket.get("category"),
        expected=case.expected_ticket_category,
    )
    ticket_priority_passed = _optional_equal(
        actual=ticket.get("priority"),
        expected=case.expected_ticket_priority,
    )
    ticket_escalation_passed = _optional_equal(
        actual=ticket.get("should_escalate"),
        expected=case.expected_ticket_should_escalate,
    )
    human_approval_passed = _optional_equal(
        actual=response.get("human_approval_required"),
        expected=case.expected_human_approval_required,
    )
    email_draft_passed = _optional_equal(
        actual=response.get("email_draft") is not None,
        expected=case.expected_email_draft_present,
    )
    action_statuses_passed = _action_statuses_passed(
        expected=case.expected_action_statuses,
        actual=actual_action_statuses,
    )
    forbidden_actions_passed = not completed_forbidden_actions

    failure_reasons = _build_failure_reasons(
        route_passed=route_passed,
        answer_passed=answer_passed,
        retrieval_status_passed=retrieval_status_passed,
        source_count_passed=source_count_passed,
        min_source_count_passed=min_source_count_passed,
        source_titles_passed=source_titles_passed,
        ticket_category_passed=ticket_category_passed,
        ticket_priority_passed=ticket_priority_passed,
        ticket_escalation_passed=ticket_escalation_passed,
        human_approval_passed=human_approval_passed,
        email_draft_passed=email_draft_passed,
        action_statuses_passed=action_statuses_passed,
        forbidden_actions_passed=forbidden_actions_passed,
    )

    return AgentEvalResult(
        case_id=case.id,
        passed=not failure_reasons,
        failure_reasons=failure_reasons,
        expected_route=case.expected_route,
        expected_answer_contains=case.expected_answer_contains,
        expected_retrieval_status=case.expected_retrieval_status,
        expected_source_count=case.expected_source_count,
        expected_min_source_count=case.expected_min_source_count,
        expected_source_titles=case.expected_source_titles,
        expected_ticket_category=case.expected_ticket_category,
        expected_ticket_priority=case.expected_ticket_priority,
        expected_ticket_should_escalate=case.expected_ticket_should_escalate,
        expected_human_approval_required=case.expected_human_approval_required,
        expected_email_draft_present=case.expected_email_draft_present,
        expected_action_statuses=case.expected_action_statuses,
        forbidden_completed_actions=case.forbidden_completed_actions,
        requires_agent_router_provider=case.requires_agent_router_provider,
        actual_answer=answer,
        actual_retrieval_status=response.get("retrieval_status"),
        actual_source_count=len(sources),
        actual_source_titles=actual_source_titles,
        actual_route=response.get("route"),
        actual_ticket_category=ticket.get("category"),
        actual_ticket_priority=ticket.get("priority"),
        actual_ticket_should_escalate=ticket.get("should_escalate"),
        actual_human_approval_required=response.get("human_approval_required"),
        actual_email_draft_present=response.get("email_draft") is not None,
        actual_action_statuses=actual_action_statuses,
        completed_forbidden_actions=completed_forbidden_actions,
        actual_router_provider=router.get("provider") if isinstance(router, dict) else None,
        actual_router_model=router.get("model") if isinstance(router, dict) else None,
        actual_router_prompt_tokens=_optional_int(router_usage.get("prompt_tokens")),
        actual_router_completion_tokens=_optional_int(
            router_usage.get("completion_tokens")
        ),
        actual_router_total_tokens=_optional_int(router_usage.get("total_tokens")),
        actual_router_estimated_cost_usd=_optional_float(
            router_usage.get("estimated_cost_usd")
        ),
        latency_ms=latency_ms,
        response=response,
    )


def build_summary(results: list[AgentEvalResult]) -> dict[str, float | int | None]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed
    average_latency = (
        sum(result.latency_ms for result in results) / total if total else 0
    )
    router_prompt_tokens = sum(result.actual_router_prompt_tokens or 0 for result in results)
    router_completion_tokens = sum(
        result.actual_router_completion_tokens or 0 for result in results
    )
    router_total_tokens = sum(result.actual_router_total_tokens or 0 for result in results)
    router_costs = [
        result.actual_router_estimated_cost_usd
        for result in results
        if result.actual_router_estimated_cost_usd is not None
    ]
    return {
        "cases_evaluated": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "average_latency_ms": round(average_latency, 2),
        "router_prompt_tokens": router_prompt_tokens,
        "router_completion_tokens": router_completion_tokens,
        "router_total_tokens": router_total_tokens,
        "router_estimated_cost_usd": (
            round(sum(router_costs), 8) if router_costs else None
        ),
    }


def run_eval(
    *,
    base_url: str,
    dataset_path: Path,
    report_dir: Path,
    max_cases: int | None = None,
    document_id: str | None = None,
    document_manifest_path: Path | None = None,
) -> tuple[dict[str, float | int | None], Path, Path]:
    cases = load_dataset(dataset_path, max_cases=max_cases)
    manifest_document_ids = load_document_manifest(document_manifest_path)
    results: list[AgentEvalResult] = []
    with httpx.Client(base_url=base_url, timeout=30) as client:
        if _requires_health_preflight(cases):
            health_response = client.get("/health")
            health_response.raise_for_status()
            validate_agent_eval_environment(
                cases=cases,
                dependencies=health_response.json().get("dependencies", {}),
            )
        for case in cases:
            document_ids = resolve_document_ids(
                case=case,
                document_id=document_id,
                manifest_document_ids=manifest_document_ids,
            )
            payload = {
                "message": case.message,
                "mode": case.mode,
                "top_k": case.top_k,
                "document_ids": document_ids,
            }
            started = perf_counter()
            response = client.post("/agent/respond", json=payload)
            latency_ms = (perf_counter() - started) * 1000
            response.raise_for_status()
            results.append(
                evaluate_response(
                    case=case,
                    response=response.json(),
                    latency_ms=latency_ms,
                )
            )

    summary = build_summary(results)
    json_path, md_path = write_reports(
        summary=summary,
        results=results,
        dataset_path=dataset_path,
        report_dir=report_dir,
    )
    return summary, json_path, md_path


def write_reports(
    *,
    summary: dict[str, float | int | None],
    results: list[AgentEvalResult],
    dataset_path: Path,
    report_dir: Path,
) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = report_dir / f"agent-workflow-eval-{timestamp}.json"
    md_path = report_dir / f"agent-workflow-eval-{timestamp}.md"
    json_payload = {
        "dataset_path": str(dataset_path),
        "summary": summary,
        "results": [_result_to_dict(result) for result in results],
    }
    json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown_report(summary, results), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic evals against /agent/respond.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--dataset-path", default="evals/initial_agent_workflow.jsonl")
    parser.add_argument("--report-dir", default="reports/evals")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--document-manifest-path", default=None)
    parser.add_argument(
        "--no-fail-on-regression",
        action="store_true",
        help="Write reports but exit 0 even when one or more workflow checks fail.",
    )
    args = parser.parse_args()

    try:
        summary, json_path, md_path = run_eval(
            base_url=args.base_url,
            dataset_path=Path(args.dataset_path),
            report_dir=Path(args.report_dir),
            max_cases=args.max_cases,
            document_id=args.document_id,
            document_manifest_path=(
                Path(args.document_manifest_path)
                if args.document_manifest_path is not None
                else None
            ),
        )
    except httpx.ConnectError:
        print(f"Could not connect to API at {args.base_url}. Is the local API running?")
        return 2
    except httpx.HTTPStatusError as exc:
        print(f"Agent workflow evaluation request failed: {exc.response.status_code}")
        print(exc.response.text)
        return 2
    except httpx.RequestError as exc:
        print(f"Agent workflow evaluation request failed: {exc}")
        return 2
    except RuntimeError as exc:
        print(f"Agent workflow evaluation failed: {exc}")
        return 2

    print("Agent workflow evaluation complete.")
    print(json.dumps(summary, indent=2))
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    if summary["failed"] and not args.no_fail_on_regression:
        return 1
    return 0


def _case_from_payload(payload: dict[str, Any], line_number: int) -> AgentEvalCase:
    try:
        return AgentEvalCase(
            id=payload["id"],
            message=payload["message"],
            mode=payload.get("mode", "auto"),
            document_ids=list(payload.get("document_ids", [])),
            top_k=payload.get("top_k"),
            expected_answer_contains=list(payload.get("expected_answer_contains", [])),
            expected_retrieval_status=payload.get("expected_retrieval_status"),
            expected_source_count=payload.get("expected_source_count"),
            expected_min_source_count=payload.get("expected_min_source_count"),
            expected_source_titles=list(payload.get("expected_source_titles", [])),
            expected_route=payload["expected_route"],
            expected_ticket_category=payload.get("expected_ticket_category"),
            expected_ticket_priority=payload.get("expected_ticket_priority"),
            expected_ticket_should_escalate=payload.get("expected_ticket_should_escalate"),
            expected_human_approval_required=payload.get("expected_human_approval_required"),
            expected_email_draft_present=payload.get("expected_email_draft_present"),
            expected_action_statuses=dict(payload.get("expected_action_statuses", {})),
            forbidden_completed_actions=list(payload.get("forbidden_completed_actions", [])),
            requires_agent_router_provider=payload.get("requires_agent_router_provider"),
        )
    except KeyError as exc:
        raise RuntimeError(
            f"Missing required field {exc!s} in {payload.get('id', line_number)!r}."
        ) from exc


def _optional_equal(*, actual: object, expected: object) -> bool:
    return expected is None or actual == expected


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def load_document_manifest(manifest_path: Path | None) -> dict[str, str]:
    if manifest_path is None:
        return {}
    if not manifest_path.exists():
        raise RuntimeError(f"Document manifest does not exist: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = payload.get("documents") or []
    return {
        str(document["title"]): str(document["document_id"])
        for document in documents
        if document.get("title") and document.get("document_id")
    }


def resolve_document_ids(
    *,
    case: AgentEvalCase,
    document_id: str | None,
    manifest_document_ids: dict[str, str],
) -> list[str]:
    if document_id:
        return [document_id]
    if case.document_ids:
        return case.document_ids
    if not manifest_document_ids:
        return []
    missing_titles = [
        title for title in case.expected_source_titles if title not in manifest_document_ids
    ]
    if missing_titles:
        raise RuntimeError(
            f"Document manifest is missing IDs for case {case.id}: "
            f"{', '.join(missing_titles)}"
        )
    return [
        manifest_document_ids[title]
        for title in case.expected_source_titles
    ]


def validate_agent_eval_environment(
    *,
    cases: list[AgentEvalCase],
    dependencies: dict[str, str],
) -> None:
    if _expects_simulated_n8n_webhook(cases):
        actual_n8n_status = dependencies.get("n8n", "unknown")
        if actual_n8n_status == "live":
            raise RuntimeError(
                "Agent eval dataset expects notify_n8n_webhook=simulated, "
                "but /health reports n8n=live. Set N8N_WEBHOOK_MODE=simulated "
                "or use the controlled n8n smoke test for live webhook dispatch."
            )

    required_router_providers = {
        case.requires_agent_router_provider
        for case in cases
        if case.requires_agent_router_provider is not None
    }
    if not required_router_providers:
        return
    if len(required_router_providers) > 1:
        raise RuntimeError(
            "Agent eval dataset requires multiple router providers: "
            f"{', '.join(sorted(required_router_providers))}"
        )

    required_router_provider = required_router_providers.pop()
    actual_router_provider = dependencies.get("agent_router", "unknown")
    if actual_router_provider != required_router_provider:
        raise RuntimeError(
            "Agent eval dataset requires "
            f"agent_router={required_router_provider}, but /health reports "
            f"agent_router={actual_router_provider}."
        )


def _requires_health_preflight(cases: list[AgentEvalCase]) -> bool:
    return any(case.requires_agent_router_provider is not None for case in cases) or (
        _expects_simulated_n8n_webhook(cases)
    )


def _expects_simulated_n8n_webhook(cases: list[AgentEvalCase]) -> bool:
    return any(
        case.expected_action_statuses.get("notify_n8n_webhook") == "simulated"
        for case in cases
    )


def _action_statuses(response: dict[str, Any]) -> dict[str, str]:
    statuses = {}
    for action in response.get("actions", []):
        if isinstance(action, dict) and "name" in action and "status" in action:
            statuses[str(action["name"])] = str(action["status"])
    return statuses


def _source_titles(sources: object) -> list[str]:
    if not isinstance(sources, list):
        return []
    return [
        str(source["title"])
        for source in sources
        if isinstance(source, dict) and source.get("title")
    ]


def _action_statuses_passed(
    *,
    expected: dict[str, str],
    actual: dict[str, str],
) -> bool:
    return all(actual.get(action_name) == status for action_name, status in expected.items())


def _build_failure_reasons(
    *,
    route_passed: bool,
    answer_passed: bool,
    retrieval_status_passed: bool,
    source_count_passed: bool,
    min_source_count_passed: bool,
    source_titles_passed: bool,
    ticket_category_passed: bool,
    ticket_priority_passed: bool,
    ticket_escalation_passed: bool,
    human_approval_passed: bool,
    email_draft_passed: bool,
    action_statuses_passed: bool,
    forbidden_actions_passed: bool,
) -> list[str]:
    reasons = []
    if not route_passed:
        reasons.append("route")
    if not answer_passed:
        reasons.append("answer")
    if not retrieval_status_passed:
        reasons.append("retrieval_status")
    if not source_count_passed:
        reasons.append("source_count")
    if not min_source_count_passed:
        reasons.append("min_source_count")
    if not source_titles_passed:
        reasons.append("source_titles")
    if not ticket_category_passed:
        reasons.append("ticket_category")
    if not ticket_priority_passed:
        reasons.append("ticket_priority")
    if not ticket_escalation_passed:
        reasons.append("ticket_should_escalate")
    if not human_approval_passed:
        reasons.append("human_approval_required")
    if not email_draft_passed:
        reasons.append("email_draft")
    if not action_statuses_passed:
        reasons.append("action_statuses")
    if not forbidden_actions_passed:
        reasons.append("forbidden_completed_actions")
    return reasons


def _result_to_dict(result: AgentEvalResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "passed": result.passed,
        "failure_reasons": result.failure_reasons,
        "expected": {
            "route": result.expected_route,
            "answer_contains": result.expected_answer_contains,
            "retrieval_status": result.expected_retrieval_status,
            "source_count": result.expected_source_count,
            "min_source_count": result.expected_min_source_count,
            "source_titles": result.expected_source_titles,
            "ticket_category": result.expected_ticket_category,
            "ticket_priority": result.expected_ticket_priority,
            "ticket_should_escalate": result.expected_ticket_should_escalate,
            "human_approval_required": result.expected_human_approval_required,
            "email_draft_present": result.expected_email_draft_present,
            "action_statuses": result.expected_action_statuses,
            "forbidden_completed_actions": result.forbidden_completed_actions,
            "requires_agent_router_provider": result.requires_agent_router_provider,
        },
        "actual": {
            "route": result.actual_route,
            "answer": result.actual_answer,
            "retrieval_status": result.actual_retrieval_status,
            "source_count": result.actual_source_count,
            "source_titles": result.actual_source_titles,
            "ticket_category": result.actual_ticket_category,
            "ticket_priority": result.actual_ticket_priority,
            "ticket_should_escalate": result.actual_ticket_should_escalate,
            "human_approval_required": result.actual_human_approval_required,
            "email_draft_present": result.actual_email_draft_present,
            "action_statuses": result.actual_action_statuses,
            "completed_forbidden_actions": result.completed_forbidden_actions,
            "router_provider": result.actual_router_provider,
            "router_model": result.actual_router_model,
            "router_prompt_tokens": result.actual_router_prompt_tokens,
            "router_completion_tokens": result.actual_router_completion_tokens,
            "router_total_tokens": result.actual_router_total_tokens,
            "router_estimated_cost_usd": result.actual_router_estimated_cost_usd,
        },
        "latency_ms": round(result.latency_ms, 2),
        "response": result.response,
    }


def _build_markdown_report(
    summary: dict[str, float | int | None],
    results: list[AgentEvalResult],
) -> str:
    lines = [
        "# Agent Workflow Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Cases evaluated: {summary['cases_evaluated']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Pass rate: {summary['pass_rate']}",
        f"- Average latency ms: {summary['average_latency_ms']}",
        f"- Router prompt tokens: {summary['router_prompt_tokens']}",
        f"- Router completion tokens: {summary['router_completion_tokens']}",
        f"- Router total tokens: {summary['router_total_tokens']}",
        f"- Router estimated cost USD: {summary['router_estimated_cost_usd']}",
        "",
        "## Cases",
        "",
    ]
    for result in results:
        status = "pass" if result.passed else "fail"
        lines.extend(
            [
                f"### {result.case_id}: {status}",
                "",
                f"- Expected route: {result.expected_route}",
                f"- Actual route: {result.actual_route}",
                f"- Expected retrieval status: {result.expected_retrieval_status}",
                f"- Actual retrieval status: {result.actual_retrieval_status}",
                f"- Expected source count: {result.expected_source_count}",
                f"- Actual source count: {result.actual_source_count}",
                f"- Expected min source count: {result.expected_min_source_count}",
                f"- Expected source titles: {result.expected_source_titles}",
                f"- Actual source titles: {result.actual_source_titles}",
                f"- Expected action statuses: {result.expected_action_statuses}",
                f"- Actual action statuses: {result.actual_action_statuses}",
                f"- Actual router provider: {result.actual_router_provider}",
                f"- Actual router model: {result.actual_router_model}",
                f"- Actual router total tokens: {result.actual_router_total_tokens}",
                (
                    "- Actual router estimated cost USD: "
                    f"{result.actual_router_estimated_cost_usd}"
                ),
                (
                    "- Required agent router provider: "
                    f"{result.requires_agent_router_provider}"
                ),
                f"- Completed forbidden actions: {result.completed_forbidden_actions}",
                f"- Latency ms: {round(result.latency_ms, 2)}",
                "",
            ]
        )
        if not result.passed:
            lines.extend(
                [
                    f"- Failure reasons: {', '.join(result.failure_reasons)}",
                    f"- Expected ticket category: {result.expected_ticket_category}",
                    f"- Actual ticket category: {result.actual_ticket_category}",
                    f"- Expected ticket priority: {result.expected_ticket_priority}",
                    f"- Actual ticket priority: {result.actual_ticket_priority}",
                    f"- Expected answer contains: {result.expected_answer_contains}",
                    f"- Actual answer: {result.actual_answer}",
                    "",
                ]
            )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
