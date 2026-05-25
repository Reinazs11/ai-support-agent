import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from app.rag.chat_models import INSUFFICIENT_CONTEXT_ANSWER

SEMANTIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "in",
    "is",
    "it",
    "its",
    "may",
    "must",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "they",
    "to",
    "with",
}


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    expected_status: str | None
    expected_answer_contains: list[str]
    expected_answer_contains_any: list[list[str]]
    forbidden_answer_contains: list[str]
    max_answer_chars: int | None
    expected_source_titles: list[str]
    document_ids: list[str]
    top_k: int


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    passed: bool
    status_passed: bool
    answer_passed: bool
    answer_correctness_passed: bool
    source_passed: bool
    quality_passed: bool
    quality_score: float
    quality_failure_reasons: list[str]
    semantic_evaluated: bool
    semantic_passed: bool
    semantic_score: float | None
    semantic_threshold: float | None
    semantic_provider: str
    semantic_rationale: str
    semantic_failure_reasons: list[str]
    failure_reasons: list[str]
    expected_status: str | None
    expected_answer_contains: list[str]
    expected_answer_contains_any: list[list[str]]
    forbidden_answer_contains: list[str]
    max_answer_chars: int | None
    expected_source_titles: list[str]
    actual_status: str | None
    actual_answer: str
    actual_source_titles: list[str]
    latency_ms: float
    estimated_cost_usd: float | None
    response: dict[str, Any]


@dataclass(frozen=True)
class SemanticJudgeResult:
    evaluated: bool
    passed: bool
    score: float | None
    threshold: float | None
    provider: str
    rationale: str
    failure_reasons: list[str]


class DisabledSemanticJudge:
    provider = "disabled"
    threshold = None

    def evaluate(self, case: EvalCase, answer: str) -> SemanticJudgeResult:
        return SemanticJudgeResult(
            evaluated=False,
            passed=True,
            score=None,
            threshold=None,
            provider=self.provider,
            rationale="Semantic judge disabled.",
            failure_reasons=[],
        )


class HeuristicSemanticJudge:
    provider = "heuristic"

    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def evaluate(self, case: EvalCase, answer: str) -> SemanticJudgeResult:
        if case.expected_status in {"insufficient_context", "no_results"}:
            return self._skipped("Case expects fallback behavior.")

        fact_groups = _semantic_fact_groups(case)
        if not fact_groups:
            return self._skipped("Case has no expected answer facts.")

        scores = [
            max(_semantic_overlap_score(variant=variant, answer=answer) for variant in group)
            for group in fact_groups
        ]
        score = round(sum(scores) / len(scores), 4)
        matched = sum(1 for item_score in scores if item_score >= self.threshold)
        passed = score >= self.threshold
        failure_reasons = [] if passed else ["expected_facts_below_threshold"]
        return SemanticJudgeResult(
            evaluated=True,
            passed=passed,
            score=score,
            threshold=self.threshold,
            provider=self.provider,
            rationale=(
                f"Matched {matched}/{len(scores)} fact groups with average "
                f"semantic score {score}."
            ),
            failure_reasons=failure_reasons,
        )

    def _skipped(self, rationale: str) -> SemanticJudgeResult:
        return SemanticJudgeResult(
            evaluated=False,
            passed=True,
            score=None,
            threshold=self.threshold,
            provider=self.provider,
            rationale=rationale,
            failure_reasons=[],
        )


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


def evaluate_response(
    case: EvalCase,
    response: dict[str, Any],
    latency_ms: float,
    semantic_judge: DisabledSemanticJudge | HeuristicSemanticJudge | None = None,
) -> EvalResult:
    semantic_judge = semantic_judge or DisabledSemanticJudge()
    answer = str(response.get("answer", ""))
    normalized_answer = _normalize_answer_text(answer)
    sources = response.get("sources") or []
    source_titles = {str(source.get("title", "")) for source in sources}
    usage = response.get("usage") or {}
    actual_status = response.get("retrieval_status")

    status_passed = case.expected_status is None or actual_status == case.expected_status
    required_terms_passed = all(
        _normalize_answer_text(expected) in normalized_answer
        for expected in case.expected_answer_contains
    )
    variant_groups_passed = all(
        any(_normalize_answer_text(variant) in normalized_answer for variant in variant_group)
        for variant_group in case.expected_answer_contains_any
    )
    answer_passed = required_terms_passed and variant_groups_passed
    source_passed = all(title in source_titles for title in case.expected_source_titles)
    quality_passed, quality_score, quality_failure_reasons = _evaluate_answer_quality(
        case=case,
        normalized_answer=normalized_answer,
        answer=answer,
    )
    semantic_result = semantic_judge.evaluate(case=case, answer=answer)
    answer_correctness_passed = (
        semantic_result.passed if semantic_result.evaluated else answer_passed
    )
    failure_reasons = _build_failure_reasons(
        status_passed=status_passed,
        answer_correctness_passed=answer_correctness_passed,
        source_passed=source_passed,
        quality_passed=quality_passed,
        semantic_evaluated=semantic_result.evaluated,
    )
    passed = (
        status_passed
        and answer_correctness_passed
        and source_passed
        and quality_passed
    )

    return EvalResult(
        case_id=case.id,
        passed=passed,
        status_passed=status_passed,
        answer_passed=answer_passed,
        answer_correctness_passed=answer_correctness_passed,
        source_passed=source_passed,
        quality_passed=quality_passed,
        quality_score=quality_score,
        quality_failure_reasons=quality_failure_reasons,
        semantic_evaluated=semantic_result.evaluated,
        semantic_passed=semantic_result.passed,
        semantic_score=semantic_result.score,
        semantic_threshold=semantic_result.threshold,
        semantic_provider=semantic_result.provider,
        semantic_rationale=semantic_result.rationale,
        semantic_failure_reasons=semantic_result.failure_reasons,
        failure_reasons=failure_reasons,
        expected_status=case.expected_status,
        expected_answer_contains=case.expected_answer_contains,
        expected_answer_contains_any=case.expected_answer_contains_any,
        forbidden_answer_contains=case.forbidden_answer_contains,
        max_answer_chars=case.max_answer_chars,
        expected_source_titles=case.expected_source_titles,
        actual_status=str(actual_status) if actual_status is not None else None,
        actual_answer=answer,
        actual_source_titles=sorted(source_titles),
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
    quality_passed = sum(1 for result in results if result.quality_passed)
    semantic_results = [result for result in results if result.semantic_evaluated]
    semantic_passed = sum(1 for result in semantic_results if result.semantic_passed)
    total_cost = sum(result.estimated_cost_usd or 0 for result in results)
    average_latency = (
        sum(result.latency_ms for result in results) / total if total else 0
    )
    average_quality_score = (
        sum(result.quality_score for result in results) / total if total else 0
    )
    average_semantic_score = (
        sum(result.semantic_score or 0 for result in semantic_results)
        / len(semantic_results)
        if semantic_results
        else 0
    )
    return {
        "questions_evaluated": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "quality_passed": quality_passed,
        "average_quality_score": round(average_quality_score, 4),
        "semantic_evaluated": len(semantic_results),
        "semantic_passed": semantic_passed,
        "average_semantic_score": round(average_semantic_score, 4),
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
    document_manifest_path: Path | None,
    max_total_cost_usd: float,
    semantic_judge_provider: str = "disabled",
    semantic_threshold: float = 0.8,
) -> tuple[dict[str, float | int], Path, Path]:
    cases = load_dataset(dataset_path, max_questions=max_questions)
    manifest_document_ids = load_document_manifest(document_manifest_path)
    semantic_judge = build_semantic_judge(
        provider=semantic_judge_provider,
        threshold=semantic_threshold,
    )
    results = []
    total_cost = 0.0

    with httpx.Client(base_url=base_url, timeout=60) as client:
        for case in cases:
            document_ids = resolve_document_ids(
                case=case,
                document_id=document_id,
                manifest_document_ids=manifest_document_ids,
            )
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
            result = evaluate_response(
                case=case,
                response=response.json(),
                latency_ms=latency_ms,
                semantic_judge=semantic_judge,
            )
            results.append(result)
            total_cost += result.estimated_cost_usd or 0
            if total_cost > max_total_cost_usd:
                raise RuntimeError(
                    f"Evaluation cost estimate ${total_cost:.8f} exceeded limit "
                    f"${max_total_cost_usd:.8f}."
                )

    json_path, md_path = write_reports(results=results, report_dir=report_dir)
    return build_summary(results), json_path, md_path


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
    case: EvalCase,
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


def build_semantic_judge(
    *,
    provider: str,
    threshold: float,
) -> DisabledSemanticJudge | HeuristicSemanticJudge:
    if provider == "disabled":
        return DisabledSemanticJudge()
    if provider == "heuristic":
        if threshold <= 0 or threshold > 1:
            raise RuntimeError("--semantic-threshold must be greater than 0 and at most 1.")
        return HeuristicSemanticJudge(threshold=threshold)
    raise RuntimeError(f"Unsupported semantic judge provider: {provider}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RAG evals against /chat.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--dataset-path", default="evals/initial_rag.jsonl")
    parser.add_argument("--report-dir", default="reports/evals")
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--document-manifest-path", default=None)
    parser.add_argument("--max-total-cost-usd", type=float, default=0.05)
    parser.add_argument(
        "--semantic-judge",
        choices=("disabled", "heuristic"),
        default="disabled",
        help="Optional local semantic answer judge. Does not call external providers.",
    )
    parser.add_argument("--semantic-threshold", type=float, default=0.8)
    parser.add_argument("--no-fail-on-regression", action="store_true")
    args = parser.parse_args()

    try:
        summary, json_path, md_path = run_eval(
            base_url=args.base_url,
            dataset_path=Path(args.dataset_path),
            report_dir=Path(args.report_dir),
            max_questions=args.max_questions,
            document_id=args.document_id,
            document_manifest_path=(
                Path(args.document_manifest_path)
                if args.document_manifest_path is not None
                else None
            ),
            max_total_cost_usd=args.max_total_cost_usd,
            semantic_judge_provider=args.semantic_judge,
            semantic_threshold=args.semantic_threshold,
        )
    except httpx.ConnectError:
        print(f"Could not connect to API at {args.base_url}. Start the local API and retry.")
        return 1
    except httpx.HTTPStatusError as exc:
        print(f"Evaluation request failed with HTTP {exc.response.status_code}.")
        return 1
    except httpx.RequestError as exc:
        print(f"Evaluation request failed: {exc.__class__.__name__}.")
        return 1
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print("RAG evaluation complete.")
    print(json.dumps(summary, indent=2))
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    failed_results = [result for result in results_from_report(json_path) if not result["passed"]]
    if failed_results:
        print("Failed cases:")
        for result in failed_results:
            reasons = ", ".join(result["failure_reasons"])
            print(f"- {result['case_id']}: {reasons}")

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
            expected_answer_contains_any=list(payload.get("expected_answer_contains_any", [])),
            forbidden_answer_contains=list(payload.get("forbidden_answer_contains", [])),
            max_answer_chars=(
                int(payload["max_answer_chars"])
                if payload.get("max_answer_chars") is not None
                else None
            ),
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
        "answer_correctness_passed": result.answer_correctness_passed,
        "source_passed": result.source_passed,
        "quality_passed": result.quality_passed,
        "quality_score": result.quality_score,
        "quality_failure_reasons": result.quality_failure_reasons,
        "semantic": {
            "evaluated": result.semantic_evaluated,
            "passed": result.semantic_passed,
            "score": result.semantic_score,
            "threshold": result.semantic_threshold,
            "provider": result.semantic_provider,
            "rationale": result.semantic_rationale,
            "failure_reasons": result.semantic_failure_reasons,
        },
        "failure_reasons": result.failure_reasons,
        "expected": {
            "retrieval_status": result.expected_status,
            "answer_contains": result.expected_answer_contains,
            "answer_contains_any": result.expected_answer_contains_any,
            "forbidden_answer_contains": result.forbidden_answer_contains,
            "max_answer_chars": result.max_answer_chars,
            "source_titles": result.expected_source_titles,
        },
        "actual": {
            "retrieval_status": result.actual_status,
            "answer": result.actual_answer,
            "source_titles": result.actual_source_titles,
        },
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
        f"- Quality passed: {summary['quality_passed']}",
        f"- Average quality score: {summary['average_quality_score']}",
        f"- Semantic evaluated: {summary['semantic_evaluated']}",
        f"- Semantic passed: {summary['semantic_passed']}",
        f"- Average semantic score: {summary['average_semantic_score']}",
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
                f"- Deterministic answer check: {result.answer_passed}",
                f"- Answer correctness check: {result.answer_correctness_passed}",
                f"- Source check: {result.source_passed}",
                f"- Quality check: {result.quality_passed}",
                f"- Quality score: {result.quality_score}",
                f"- Semantic judge: {result.semantic_provider}",
                f"- Semantic evaluated: {result.semantic_evaluated}",
                f"- Semantic check: {result.semantic_passed}",
                f"- Semantic score: {result.semantic_score}",
                f"- Latency ms: {round(result.latency_ms, 2)}",
                f"- Estimated cost USD: {result.estimated_cost_usd}",
                "",
            ]
        )
        if not result.passed:
            lines.extend(
                [
                    f"- Failure reasons: {', '.join(result.failure_reasons)}",
                    f"- Expected status: {result.expected_status}",
                    f"- Actual status: {result.actual_status}",
                    f"- Expected answer contains: {result.expected_answer_contains}",
                    f"- Expected answer variants: {result.expected_answer_contains_any}",
                    f"- Forbidden answer contains: {result.forbidden_answer_contains}",
                    f"- Max answer chars: {result.max_answer_chars}",
                    f"- Quality failure reasons: {result.quality_failure_reasons}",
                    f"- Semantic threshold: {result.semantic_threshold}",
                    f"- Semantic rationale: {result.semantic_rationale}",
                    f"- Semantic failure reasons: {result.semantic_failure_reasons}",
                    f"- Actual answer: {result.actual_answer}",
                    f"- Expected source titles: {result.expected_source_titles}",
                    f"- Actual source titles: {result.actual_source_titles}",
                    "",
                ]
            )
    return "\n".join(lines)


def _build_failure_reasons(
    *,
    status_passed: bool,
    answer_correctness_passed: bool,
    source_passed: bool,
    quality_passed: bool,
    semantic_evaluated: bool,
) -> list[str]:
    reasons = []
    if not status_passed:
        reasons.append("retrieval_status")
    if not answer_correctness_passed:
        reasons.append("semantic" if semantic_evaluated else "answer")
    if not source_passed:
        reasons.append("sources")
    if not quality_passed:
        reasons.append("quality")
    return reasons


def _evaluate_answer_quality(
    *,
    case: EvalCase,
    normalized_answer: str,
    answer: str,
) -> tuple[bool, float, list[str]]:
    fallback_answer = _normalize_answer_text(INSUFFICIENT_CONTEXT_ANSWER)
    checks = {
        "answer_present": bool(normalized_answer),
        "fallback_behavior": _fallback_quality_passed(
            expected_status=case.expected_status,
            normalized_answer=normalized_answer,
            fallback_answer=fallback_answer,
        ),
        "forbidden_terms": all(
            _normalize_answer_text(term) not in normalized_answer
            for term in case.forbidden_answer_contains
        ),
        "answer_length": (
            case.max_answer_chars is None or len(answer) <= case.max_answer_chars
        ),
    }
    failed_reasons = [name for name, passed in checks.items() if not passed]
    score = round(sum(1 for passed in checks.values() if passed) / len(checks), 4)
    return not failed_reasons, score, failed_reasons


def _fallback_quality_passed(
    *,
    expected_status: str | None,
    normalized_answer: str,
    fallback_answer: str,
) -> bool:
    if expected_status in {"insufficient_context", "no_results"}:
        return normalized_answer == fallback_answer
    if expected_status == "generated":
        return fallback_answer not in normalized_answer
    return True


def _semantic_fact_groups(case: EvalCase) -> list[list[str]]:
    fact_groups = [[expected] for expected in case.expected_answer_contains]
    fact_groups.extend(case.expected_answer_contains_any)
    return fact_groups


def _semantic_overlap_score(*, variant: str, answer: str) -> float:
    normalized_variant = _normalize_answer_text(variant)
    normalized_answer = _normalize_answer_text(answer)
    if normalized_variant and normalized_variant in normalized_answer:
        return 1.0

    variant_tokens = set(_semantic_tokens(variant))
    if not variant_tokens:
        return 0.0

    answer_tokens = set(_semantic_tokens(answer))
    return len(variant_tokens & answer_tokens) / len(variant_tokens)


def _semantic_tokens(value: str) -> list[str]:
    return [
        token
        for token in _normalize_answer_text(value).split()
        if token not in SEMANTIC_STOPWORDS
    ]


def _normalize_answer_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    without_apostrophes = without_marks.replace("'", "").replace("\u2019", "")
    alphanumeric_words = re.sub(r"[^a-z0-9]+", " ", without_apostrophes)
    return " ".join(alphanumeric_words.split())


def results_from_report(json_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return list(payload.get("results", []))


if __name__ == "__main__":
    sys.exit(main())
