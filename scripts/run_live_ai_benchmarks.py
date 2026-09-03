"""Run Ticket-Genie's golden set against live Azure OpenAI and AI Search."""

# ruff: noqa: E402 -- backend is intentionally added to sys.path before app imports.

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# The application uses ``backend`` as its import root in production and tests.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from agents.category_agent import ALLOWED_CATEGORIES
from agents.chatbot_agent import decide
from agents.knowledge_agent import answer_from_context
from agents.orchestrator import classify_ticket
from models.chatbot import ChatScope
from scripts.run_ai_benchmarks import DEFAULT_THRESHOLDS, markdown_report
from services.knowledge_service import KnowledgeDocument, default_knowledge_retriever

SCOPES = ["General", "HR", "IT", "Accounting", "WorkplaceOperations", "UpperManagement"]
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "how",
    "in",
    "is",
    "of",
    "the",
    "to",
    "what",
    "where",
    "who",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOPWORDS
    }


def _configured() -> bool:
    return all(
        os.getenv(name)
        for name in (
            "GROUP1OPENAIENDPOINT",
            "GROUP1OPENAIAPIKEY",
            "AISEARCH_ENDPOINT",
            "AISEARCH_APIKEY",
        )
    )


def run_live(data: dict, limit: int | None = None) -> tuple[dict, dict, dict]:
    failures = {name: [] for name in DEFAULT_THRESHOLDS}
    predictions: dict[str, list[dict]] = {name: [] for name in data}

    refusal_rows = data["refusal"][:limit]
    refusal_hits = 0
    for row in refusal_rows:
        decision = decide(
            row["prompt"],
            standard_categories=[
                item for values in ALLOWED_CATEGORIES.values() for item in values
            ],
            leave_types=["PTO", "Sick", "Parental", "Bereavement", "Unpaid"],
            ticket_departments=list(ALLOWED_CATEGORIES),
            ticket_priorities=["Low", "Medium", "High", "Critical"],
            employee_departments=list(ALLOWED_CATEGORIES),
            employee_roles=["Employee", "Admin", "Super Admin"],
        )
        predicted = decision.scope == ChatScope.OUT_OF_SCOPE
        correct = predicted == row["expected_refusal"]
        refusal_hits += correct
        predictions["refusal"].append(
            {"id": row["id"], "predicted_refusal": predicted, "correct": correct}
        )
        if not correct:
            failures["refusal_correctness"].append(row["id"])

    routing_rows = data["routing"][:limit]
    routing_hits = 0
    for row in routing_rows:
        result = classify_ticket(row["prompt"], row["prompt"])
        correct = result.department == row["expected"]
        routing_hits += correct
        predictions["routing"].append(
            {"id": row["id"], "predicted": result.department, "correct": correct}
        )
        if not correct:
            failures["routing_accuracy"].append(row["id"])

    retrieval_rows = data["retrieval"][:limit]
    retrieval_hits = 0
    for row in retrieval_rows:
        documents = default_knowledge_retriever.search(row["query"], SCOPES)
        searchable = " ".join(
            f"{doc.source} {doc.content}" for doc in documents[:5]
        ).lower()
        query_terms = _tokens(row["query"])
        matched = sorted(term for term in query_terms if term in searchable)
        hit = bool(matched)
        retrieval_hits += hit
        predictions["retrieval"].append(
            {
                "id": row["id"],
                "document_ids": [doc.id for doc in documents[:5]],
                "matched_terms": matched,
                "hit": hit,
            }
        )
        if not hit:
            failures["retrieval_hit_at_5"].append(row["id"])

    grounded_rows = data["grounded_answers"][:limit]
    answer_rows = data["answers"][:limit]
    grounding_scores: list[float] = []
    answer_hits = 0
    for grounded_row, answer_row in zip(grounded_rows, answer_rows, strict=True):
        document = KnowledgeDocument(
            id=grounded_row["id"],
            content=grounded_row["context"],
            scope="General",
            source="benchmark",
        )
        result = answer_from_context(answer_row["question"], [document])
        answer_tokens = _tokens(result.answer)
        context_tokens = _tokens(grounded_row["context"])
        grounding = len(answer_tokens & context_tokens) / max(len(answer_tokens), 1)
        grounding_scores.append(grounding)
        required = [term.lower() for term in answer_row["required_terms"]]
        accurate = all(term in result.answer.lower() for term in required)
        answer_hits += accurate
        predictions["grounded_answers"].append(
            {
                "id": grounded_row["id"],
                "answer": result.answer,
                "verified": result.verified,
                "groundedness": grounding,
            }
        )
        predictions["answers"].append(
            {"id": answer_row["id"], "answer": result.answer, "correct": accurate}
        )
        if grounding < DEFAULT_THRESHOLDS["groundedness"]:
            failures["groundedness"].append(grounded_row["id"])
        if not accurate:
            failures["answer_accuracy"].append(answer_row["id"])

    metrics = {
        "refusal_correctness": refusal_hits / len(refusal_rows),
        "groundedness": sum(grounding_scores) / len(grounding_scores),
        "routing_accuracy": routing_hits / len(routing_rows),
        "retrieval_hit_at_5": retrieval_hits / len(retrieval_rows),
        "answer_accuracy": answer_hits / len(answer_rows),
    }
    return metrics, failures, predictions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("benchmarks/ai_eval_cases.json")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/ai-benchmarks-live")
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Cases to run per metric (default: 5; use 36 for the full suite).",
    )
    args = parser.parse_args()
    if not _configured():
        print(
            "Live benchmark requires Azure OpenAI and AI Search configuration.",
            file=sys.stderr,
        )
        return 2
    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    metrics, failures, predictions = run_live(data, args.limit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = markdown_report(metrics, failures)
    payload = {
        "mode": "live",
        "metrics": metrics,
        "thresholds": DEFAULT_THRESHOLDS,
        "failed_cases": failures,
        "predictions": predictions,
    }
    (args.output_dir / "results.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "summary.md").write_text(report, encoding="utf-8")
    print(report)
    return (
        1
        if any(metrics[name] < gate for name, gate in DEFAULT_THRESHOLDS.items())
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
