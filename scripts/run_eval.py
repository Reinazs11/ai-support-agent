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
class EvalCase:
    id: str
    question: str
    expected_status: str | None
    expected_answer_contains: list[str]
    expected_source_titles: list[str]
    document_ids: list[str]
    top_k: int


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    passed: bool
    status_passed: bool
    answer_passed: bool
    source_passed: bool
    latency_ms: float
    estimated_cost_usd: float | None
    response: dict[str, Any]


def load_dataset(path: Path, max_questions: int | None = None) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open(encoding="utf-8") as dataset_file:
        for line_number, line in enumerate(dataset_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            cases.append(_case_from_payload(payload=payload, line_number=line_number))
            if max_questions is not None and len(cases) >= max_questions:
                break
    return cases


def evaluate_response(case: EvalCase, response: dict[str, Any], latency_ms: float) -> EvalResult:
    answer = str(response.get("answer", ""))
    answer_lower = answer.lower()
    sources = response.get("sources") or []
    source_titles = {str(source.get("title", "")) for source in sources}
    usage = response.get("usage") or {}

    status_passed = case.expected_status is None or response.get("retrieval_status") == (
        case.expected_status
    )
    answer_passed = all(
        expected.lower() in answer_lower for expected in case.expected_answer_contains
    )
    source_passed = all(title in source_titles for title in case.expected_source_titles)

    return EvalResult(
        case_id=case.id,
        passed=status_passed and answer_passed and source_passed,
        status_passed=status_passed,
        answer_passed=answer_passed,
        source_passed=source_passed,
        latency_ms=latency_ms,
        estimated_cost_usd=usage.get("estimated_cost_usd"),
        response=response,
    )


def write_reports(results: list[EvalResult], report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = report_dir / f"rag-eval-{timestamp}.json"
    md_path = report_dir / f"rag-eval-{timestamp}.md"
    summary = build_summary(results)

    json_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "results": [_result_to_dict(result) for result in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    md_path.write_text(_build_markdown_report(summary=summary, results=results), encoding="utf-8")
    return json_path, md_path


def build_summary(results: list[EvalResult]) -> dict[str, float | int]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    total_cost = sum(result.estimated_cost_usd or 0 for result in results)
    average_latency = (
        sum(result.latency_ms for result in results) / total if total else 0
    )
    return {
        "questions_evaluated": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "average_latency_ms": round(average_latency, 2),
        "estimated_cost_usd": round(total_cost, 8),
    }


def run_eval(
    *,
    base_url: str,
    dataset_path: Path,
    report_dir: Path,
    max_questions: int | None,
    document_id: str | None,
    max_total_cost_usd: float,
) -> tuple[dict[str, float | int], Path, Path]:
    cases = load_dataset(dataset_path, max_questions=max_questions)
    client = httpx.Client(base_url=base_url, timeout=60)
    results = []
    total_cost = 0.0

    for case in cases:
        document_ids = [document_id] if document_id else case.document_ids
        started = perf_counter()
        response = client.post(
            "/chat",
            json={
                "question": case.question,
                "top_k": case.top_k,
                "document_ids": document_ids,
            },
        )
        latency_ms = (perf_counter() - started) * 1000
        response.raise_for_status()
        result = evaluate_response(case=case, response=response.json(), latency_ms=latency_ms)
        results.append(result)
        total_cost += result.estimated_cost_usd or 0
        if total_cost > max_total_cost_usd:
            raise RuntimeError(
                f"Evaluation cost estimate ${total_cost:.8f} exceeded limit "
                f"${max_total_cost_usd:.8f}."
            )

    json_path, md_path = write_reports(results=results, report_dir=report_dir)
    return build_summary(results), json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic RAG evals against /chat.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--dataset-path", default="evals/initial_rag.jsonl")
    parser.add_argument("--report-dir", default="reports/evals")
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--max-total-cost-usd", type=float, default=0.05)
    parser.add_argument("--no-fail-on-regression", action="store_true")
    args = parser.parse_args()

    summary, json_path, md_path = run_eval(
        base_url=args.base_url,
        dataset_path=Path(args.dataset_path),
        report_dir=Path(args.report_dir),
        max_questions=args.max_questions,
        document_id=args.document_id,
        max_total_cost_usd=args.max_total_cost_usd,
    )

    print("RAG evaluation complete.")
    print(json.dumps(summary, indent=2))
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")

    if not args.no_fail_on_regression and summary["failed"] > 0:
        return 1
    return 0


def _case_from_payload(payload: dict[str, Any], line_number: int) -> EvalCase:
    try:
        return EvalCase(
            id=str(payload["id"]),
            question=str(payload["question"]),
            expected_status=payload.get("expected_status"),
            expected_answer_contains=list(payload.get("expected_answer_contains", [])),
            expected_source_titles=list(payload.get("expected_source_titles", [])),
            document_ids=list(payload.get("document_ids", [])),
            top_k=int(payload.get("top_k", 1)),
        )
    except KeyError as exc:
        raise ValueError(f"Missing required field {exc} on dataset line {line_number}.") from exc


def _result_to_dict(result: EvalResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "passed": result.passed,
        "status_passed": result.status_passed,
        "answer_passed": result.answer_passed,
        "source_passed": result.source_passed,
        "latency_ms": round(result.latency_ms, 2),
        "estimated_cost_usd": result.estimated_cost_usd,
        "response": result.response,
    }


def _build_markdown_report(summary: dict[str, float | int], results: list[EvalResult]) -> str:
    lines = [
        "# RAG Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Questions evaluated: {summary['questions_evaluated']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Pass rate: {summary['pass_rate']}",
        f"- Average latency ms: {summary['average_latency_ms']}",
        f"- Estimated cost USD: {summary['estimated_cost_usd']}",
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
                f"- Status check: {result.status_passed}",
                f"- Answer check: {result.answer_passed}",
                f"- Source check: {result.source_passed}",
                f"- Latency ms: {round(result.latency_ms, 2)}",
                f"- Estimated cost USD: {result.estimated_cost_usd}",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
