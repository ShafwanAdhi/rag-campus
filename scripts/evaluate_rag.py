from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL_SET = PROJECT_ROOT / "data" / "evaluation" / "rag_eval_set.json"
API_DIR = PROJECT_ROOT / "apps" / "api"


def normalize(text: Any) -> str:
    normalized = str(text or "").lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def contains_any(actual_values: Iterable[str], expected_values: Iterable[str]) -> bool:
    actual = {normalize(value) for value in actual_values if value}
    expected = {normalize(value) for value in expected_values if value}
    return bool(actual & expected)


def load_eval_set(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def import_backend():
    sys.path.insert(0, str(API_DIR))
    import main

    return main


def get_best_intent(result: Dict[str, Any]) -> str:
    return (
        result.get("query_intent_adaptive_top_k", {}).get("query_intent")
        or ""
    )


def get_context_sources(result: Dict[str, Any]) -> List[str]:
    structured_sources = [
        source.get("file_name", "")
        for source in result.get("sources", [])
    ]
    if structured_sources:
        return structured_sources

    return [
        context.get("metadata", {}).get("file_name", "")
        for context in result.get("contexts", [])
    ]


def get_context_topics(result: Dict[str, Any]) -> List[str]:
    return [
        context.get("metadata", {}).get("topic", "")
        for context in result.get("contexts", [])
    ]


def key_fact_coverage(answer: str, key_facts: Iterable[str]) -> float:
    facts = [fact for fact in key_facts if str(fact).strip()]
    if not facts:
        return 1.0

    normalized_answer = normalize(answer)
    matched = [
        fact
        for fact in facts
        if normalize(fact) in normalized_answer
    ]
    return len(matched) / len(facts)


def score_case(case: Dict[str, Any], result: Dict[str, Any], elapsed_ms: int) -> Dict[str, Any]:
    actual_domains = result.get("route", {}).get("domains", []) or []
    expected_domains = case.get("expected_domains", [])
    contexts = result.get("contexts", [])
    sources = get_context_sources(result)
    topics = get_context_topics(result)
    answer = result.get("answer", "") or ""

    source_hit_at_1 = bool(contexts) and contains_any(
        sources[:1],
        case.get("expected_sources", []),
    )
    source_hit_at_3 = contains_any(sources[:3], case.get("expected_sources", []))

    return {
        "id": case["id"],
        "question": case["question"],
        "domain_ok": set(actual_domains) == set(expected_domains),
        "intent_ok": get_best_intent(result) == case.get("expected_intent"),
        "source_hit_at_1": source_hit_at_1,
        "source_hit_at_3": source_hit_at_3,
        "topic_hit_at_3": contains_any(topics[:3], case.get("expected_topics", [])),
        "key_fact_coverage": key_fact_coverage(answer, case.get("key_facts", [])),
        "domain_error": bool(result.get("domain_errors")),
        "answer_status": result.get("answer_status", ""),
        "latency_ms": elapsed_ms,
        "reported_total_ms": result.get("timings", {}).get("total_ms"),
        "actual_domains": actual_domains,
        "actual_intent": get_best_intent(result),
        "top_sources": sources[:3],
        "top_topics": topics[:3],
    }


def summarize(scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(scores)
    if total == 0:
        return {}

    def ratio(key: str) -> float:
        return sum(1 for item in scores if item[key]) / total

    return {
        "total_cases": total,
        "domain_accuracy": ratio("domain_ok"),
        "intent_accuracy": ratio("intent_ok"),
        "source_hit_at_1": ratio("source_hit_at_1"),
        "source_hit_at_3": ratio("source_hit_at_3"),
        "topic_hit_at_3": ratio("topic_hit_at_3"),
        "average_key_fact_coverage": mean(
            item["key_fact_coverage"] for item in scores
        ),
        "domain_error_rate": ratio("domain_error"),
        "average_latency_ms": round(mean(item["latency_ms"] for item in scores)),
    }


def print_table(scores: List[Dict[str, Any]]) -> None:
    print("CASE | STATUS | DOMAIN | INTENT | SRC@1 | SRC@3 | TOPIC@3 | FACTS | LATENCY")
    for item in scores:
        print(
            " | ".join(
                [
                    item["id"],
                    item["answer_status"] or "-",
                    "OK" if item["domain_ok"] else "FAIL",
                    "OK" if item["intent_ok"] else "FAIL",
                    "OK" if item["source_hit_at_1"] else "FAIL",
                    "OK" if item["source_hit_at_3"] else "FAIL",
                    "OK" if item["topic_hit_at_3"] else "FAIL",
                    f"{item['key_fact_coverage']:.2f}",
                    f"{item['latency_ms']}ms",
                ]
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate SISDAS RAG end-to-end.")
    parser.add_argument("--eval-set", type=Path, default=DEFAULT_EVAL_SET)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON results instead of a compact table.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.0,
        help="Sleep between cases to avoid LLM provider rate limits.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Retry a case when the API returns a domain/rate-limit error.",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=10.0,
        help="Base delay before retrying a failed case.",
    )
    return parser


def should_retry_result(result: Dict[str, Any]) -> bool:
    if result.get("answer_status") != "domain_error":
        return False

    error_text = normalize(json.dumps(result.get("domain_errors", {}), ensure_ascii=False))
    return any(
        marker in error_text
        for marker in (
            "429",
            "rate limit",
            "too many requests",
            "temporarily",
            "timeout",
        )
    )


def run_case_with_retries(
    backend,
    case: Dict[str, Any],
    *,
    retries: int,
    retry_delay_seconds: float,
) -> tuple[Dict[str, Any], int]:
    result = {}
    elapsed_ms = 0

    for attempt in range(retries + 1):
        started = time.perf_counter()
        result = backend.rag_answer(case["question"])
        elapsed_ms = round((time.perf_counter() - started) * 1000)

        if not should_retry_result(result) or attempt >= retries:
            return result, elapsed_ms

        time.sleep(retry_delay_seconds * (attempt + 1))

    return result, elapsed_ms


def main() -> int:
    args = build_parser().parse_args()
    cases = load_eval_set(args.eval_set)

    if args.limit is not None:
        cases = cases[: args.limit]

    backend = import_backend()
    scores = []

    for index, case in enumerate(cases):
        if index and args.delay_seconds > 0:
            time.sleep(args.delay_seconds)

        result, elapsed_ms = run_case_with_retries(
            backend,
            case,
            retries=args.retries,
            retry_delay_seconds=args.retry_delay_seconds,
        )
        scores.append(score_case(case, result, elapsed_ms))

    payload = {
        "summary": summarize(scores),
        "cases": scores,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_table(scores)
        print("\nSUMMARY")
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
