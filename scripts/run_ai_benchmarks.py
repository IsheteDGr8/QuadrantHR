"""Score Ticket-Genie's versioned AI golden set and enforce quality gates."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "for",
    "in",
    "is",
    "of",
    "the",
    "to",
    "up",
    "within",
}
DEFAULT_THRESHOLDS = {
    "refusal_correctness": 0.95,
    "groundedness": 0.80,
    "routing_accuracy": 0.90,
    "retrieval_hit_at_5": 0.90,
    "answer_accuracy": 0.90,
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOPWORDS
    }


def score(data: dict) -> tuple[dict[str, float], dict[str, list[str]]]:
    failures: dict[str, list[str]] = {name: [] for name in DEFAULT_THRESHOLDS}

    refusal = data["refusal"]
    refusal_score = sum(
        row["expected_refusal"] == row["predicted_refusal"] for row in refusal
    ) / len(refusal)
    failures["refusal_correctness"] = [
        row["id"]
        for row in refusal
        if row["expected_refusal"] != row["predicted_refusal"]
    ]

    routing = data["routing"]
    routing_score = sum(row["expected"] == row["predicted"] for row in routing) / len(
        routing
    )
    failures["routing_accuracy"] = [
        row["id"] for row in routing if row["expected"] != row["predicted"]
    ]

    retrieval = data["retrieval"]
    retrieval_hits = []
    for row in retrieval:
        hit = bool(set(row["relevant"]) & set(row["ranked"][:5]))
        retrieval_hits.append(hit)
        if not hit:
            failures["retrieval_hit_at_5"].append(row["id"])

    grounded = data["grounded_answers"]
    grounded_scores = []
    for row in grounded:
        answer_tokens = _tokens(row["answer"])
        context_tokens = _tokens(row["context"])
        item_score = len(answer_tokens & context_tokens) / max(len(answer_tokens), 1)
        grounded_scores.append(item_score)
        if item_score < DEFAULT_THRESHOLDS["groundedness"]:
            failures["groundedness"].append(row["id"])

    answers = data["answers"]
    answer_scores = []
    for row in answers:
        normalized = row["answer"].lower()
        checks = [term.lower() in normalized for term in row["required_terms"]]
        item_score = sum(checks) / len(checks)
        answer_scores.append(item_score)
        if item_score < 1:
            failures["answer_accuracy"].append(row["id"])

    metrics = {
        "refusal_correctness": refusal_score,
        "groundedness": sum(grounded_scores) / len(grounded_scores),
        "routing_accuracy": routing_score,
        "retrieval_hit_at_5": sum(retrieval_hits) / len(retrieval_hits),
        "answer_accuracy": sum(answer_scores) / len(answer_scores),
    }
    return metrics, failures


def markdown_report(metrics: dict[str, float], failures: dict[str, list[str]]) -> str:
    overall = sum(metrics.values()) / len(metrics)
    lines = [
        "# Ticket-Genie AI Benchmark Results",
        "",
        f"**Overall macro-average: {overall:.1%}**",
        "",
        "| Metric | Score | Gate | Result |",
        "|---|---:|---:|---|",
    ]
    for name, threshold in DEFAULT_THRESHOLDS.items():
        value = metrics[name]
        result = "PASS" if value >= threshold else "FAIL"
        lines.append(
            f"| {name.replace('_', ' ').title()} | {value:.1%} | {threshold:.1%} | {result} |"
        )
    failed_ids = [item for values in failures.values() for item in values]
    lines.extend(
        ["", f"Failed cases: {', '.join(failed_ids) if failed_ids else 'None'}", ""]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("benchmarks/ai_eval_cases.json")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/ai-benchmarks")
    )
    args = parser.parse_args()

    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    metrics, failures = score(data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "metrics": metrics,
        "overall_macro_average": sum(metrics.values()) / len(metrics),
        "thresholds": DEFAULT_THRESHOLDS,
        "failed_cases": failures,
    }
    (args.output_dir / "results.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    report = markdown_report(metrics, failures)
    (args.output_dir / "summary.md").write_text(report, encoding="utf-8")
    print(report)
    return (
        1
        if any(metrics[name] < gate for name, gate in DEFAULT_THRESHOLDS.items())
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
