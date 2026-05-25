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
    expected_route: str
    expected_ticket_category: str | None
    expected_ticket_priority: str | None
    expected_ticket_should_escalate: bool | None
    expected_human_approval_required: bool | None
    expected_email_draft_present: bool | None
    expected_action_statuses: dict[str, str]
    forbidden_completed_actions: list[str]


@dataclass(frozen=True)
class AgentEvalResult:
    case_id: str
    passed: bool
    failure_reasons: list[str]
    expected_route: str
    expected_ticket_category: str | None
    expected_ticket_priority: str | None
    expected_ticket_should_escalate: bool | None
    expected_human_approval_required: bool | None
    expected_email_draft_present: bool | None
    expected_action_statuses: dict[str, str]
    forbidden_completed_actions: list[str]
    actual_route: str | None
    actual_ticket_category: str | None
    actual_ticket_priority: str | None
    actual_ticket_should_escalate: bool | None
    actual_human_approval_required: bool | None
    actual_email_draft_present: bool
    actual_action_statuses: dict[str, str]
    completed_forbidden_actions: list[str]
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

    route_passed = response.get("route") == case.expected_route
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
        expected_ticket_category=case.expected_ticket_category,
        expected_ticket_priority=case.expected_ticket_priority,
        expected_ticket_should_escalate=case.expected_ticket_should_escalate,
        expected_human_approval_required=case.expected_human_approval_required,
        expected_email_draft_present=case.expected_email_draft_present,
        expected_action_statuses=case.expected_action_statuses,
        forbidden_completed_actions=case.forbidden_completed_actions,
        actual_route=response.get("route"),
        actual_ticket_category=ticket.get("category"),
        actual_ticket_priority=ticket.get("priority"),
        actual_ticket_should_escalate=ticket.get("should_escalate"),
        actual_human_approval_required=response.get("human_approval_required"),
        actual_email_draft_present=response.get("email_draft") is not None,
        actual_action_statuses=actual_action_statuses,
        completed_forbidden_actions=completed_forbidden_actions,
        latency_ms=latency_ms,
        response=response,
    )


def build_summary(results: list[AgentEvalResult]) -> dict[str, float | int]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed
    average_latency = (
        sum(result.latency_ms for result in results) / total if total else 0
    )
    return {
        "cases_evaluated": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "average_latency_ms": round(average_latency, 2),
    }


def run_eval(
    *,
    base_url: str,
    dataset_path: Path,
    report_dir: Path,
    max_cases: int | None = None,
) -> tuple[dict[str, float | int], Path, Path]:
    cases = load_dataset(dataset_path, max_cases=max_cases)
    results: list[AgentEvalResult] = []
    with httpx.Client(base_url=base_url, timeout=30) as client:
        for case in cases:
            payload = {"message": case.message, "mode": case.mode}
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
    summary: dict[str, float | int],
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
            expected_route=payload["expected_route"],
            expected_ticket_category=payload.get("expected_ticket_category"),
            expected_ticket_priority=payload.get("expected_ticket_priority"),
            expected_ticket_should_escalate=payload.get("expected_ticket_should_escalate"),
            expected_human_approval_required=payload.get("expected_human_approval_required"),
            expected_email_draft_present=payload.get("expected_email_draft_present"),
            expected_action_statuses=dict(payload.get("expected_action_statuses", {})),
            forbidden_completed_actions=list(payload.get("forbidden_completed_actions", [])),
        )
    except KeyError as exc:
        raise RuntimeError(
            f"Missing required field {exc!s} in {payload.get('id', line_number)!r}."
        ) from exc


def _optional_equal(*, actual: object, expected: object) -> bool:
    return expected is None or actual == expected


def _action_statuses(response: dict[str, Any]) -> dict[str, str]:
    statuses = {}
    for action in response.get("actions", []):
        if isinstance(action, dict) and "name" in action and "status" in action:
            statuses[str(action["name"])] = str(action["status"])
    return statuses


def _action_statuses_passed(
    *,
    expected: dict[str, str],
    actual: dict[str, str],
) -> bool:
    return all(actual.get(action_name) == status for action_name, status in expected.items())


def _build_failure_reasons(
    *,
    route_passed: bool,
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
            "ticket_category": result.expected_ticket_category,
            "ticket_priority": result.expected_ticket_priority,
            "ticket_should_escalate": result.expected_ticket_should_escalate,
            "human_approval_required": result.expected_human_approval_required,
            "email_draft_present": result.expected_email_draft_present,
            "action_statuses": result.expected_action_statuses,
            "forbidden_completed_actions": result.forbidden_completed_actions,
        },
        "actual": {
            "route": result.actual_route,
            "ticket_category": result.actual_ticket_category,
            "ticket_priority": result.actual_ticket_priority,
            "ticket_should_escalate": result.actual_ticket_should_escalate,
            "human_approval_required": result.actual_human_approval_required,
            "email_draft_present": result.actual_email_draft_present,
            "action_statuses": result.actual_action_statuses,
            "completed_forbidden_actions": result.completed_forbidden_actions,
        },
        "latency_ms": round(result.latency_ms, 2),
        "response": result.response,
    }


def _build_markdown_report(
    summary: dict[str, float | int],
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
                f"- Expected action statuses: {result.expected_action_statuses}",
                f"- Actual action statuses: {result.actual_action_statuses}",
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
                    "",
                ]
            )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
