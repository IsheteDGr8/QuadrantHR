"""Benchmark Ticket-Genie's live priority classifier on the Kaggle 50K set."""

# ruff: noqa: E402 -- backend is intentionally added before app imports.

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from agents.orchestrator import classify_ticket

LABELS = ("low", "medium", "high")
DEFAULT_SAMPLE_COUNTS = {"low": 100, "medium": 70, "high": 30}


def ticket_text(row: dict[str, str]) -> tuple[str, str]:
    title = f"{row['product_area'].replace('_', ' ').title()} support incident"
    description = (
        f"A {row['company_size'].lower()} {row['industry']} company in "
        f"{row['region']} reported this through {row['booking_channel']}. "
        f"Customer tier: {row['customer_tier']}. "
        f"Affected users: {row['customers_affected']}; error rate: "
        f"{row['error_rate_pct']}%; downtime: {row['downtime_min']} minutes. "
        f"Payment impact: {row['payment_impact_flag']}; security incident: "
        f"{row['security_incident_flag']}; data loss: {row['data_loss_flag']}. "
        f"Recent tickets: {row['past_30d_tickets']}; recent incidents: "
        f"{row['past_90d_incidents']}; sentiment: {row['customer_sentiment']}."
    )
    return title, description


def stratified_sample(
    rows: list[dict[str, str]], seed: int = 42
) -> list[dict[str, str]]:
    rng = random.Random(seed)
    groups = {
        label: [row for row in rows if row["priority"].lower() == label]
        for label in LABELS
    }
    selected = []
    for label, count in DEFAULT_SAMPLE_COUNTS.items():
        if len(groups[label]) < count:
            raise ValueError(
                f"Dataset has only {len(groups[label])} {label} rows; {count} required"
            )
        selected.extend(rng.sample(groups[label], count))
    rng.shuffle(selected)
    return selected


def normalize_prediction(priority: str) -> str:
    value = priority.strip().lower()
    return "high" if value == "critical" else value


def calculate_metrics(records: list[dict]) -> dict:
    confusion = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    valid = [record for record in records if record.get("predicted") in LABELS]
    for record in valid:
        confusion[record["actual"]][record["predicted"]] += 1
    correct = sum(confusion[label][label] for label in LABELS)
    per_class = {}
    for label in LABELS:
        tp = confusion[label][label]
        actual_total = sum(confusion[label].values())
        predicted_total = sum(confusion[actual][label] for actual in LABELS)
        precision = tp / predicted_total if predicted_total else 0.0
        recall = tp / actual_total if actual_total else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": actual_total,
        }
    model_records = [record for record in valid if not record.get("fallback", False)]
    model_correct = sum(
        record["actual"] == record["predicted"] for record in model_records
    )
    return {
        "evaluated": len(valid),
        "accuracy": correct / len(valid) if valid else 0.0,
        "successful_model_responses": len(model_records),
        "model_response_accuracy": (
            model_correct / len(model_records) if model_records else 0.0
        ),
        "macro_precision": sum(item["precision"] for item in per_class.values()) / 3,
        "macro_recall": sum(item["recall"] for item in per_class.values()) / 3,
        "macro_f1": sum(item["f1"] for item in per_class.values()) / 3,
        "per_class": per_class,
        "confusion_matrix": confusion,
        "critical_mapped_to_high": sum(
            record.get("raw_prediction", "").lower() == "critical" for record in records
        ),
        "fallback_count": sum(record.get("fallback", False) for record in records),
    }


def write_report(metrics: dict, output: Path) -> None:
    lines = [
        "# Kaggle Support Ticket Priority Benchmark",
        "",
        f"- Evaluated rows: **{metrics['evaluated']}**",
        f"- Accuracy: **{metrics['accuracy']:.6%}**",
        f"- Successful model responses: **{metrics['successful_model_responses']}**",
        f"- Accuracy excluding infrastructure fallbacks: **{metrics['model_response_accuracy']:.6%}**",
        f"- Macro precision: **{metrics['macro_precision']:.6%}**",
        f"- Macro recall: **{metrics['macro_recall']:.6%}**",
        f"- Macro F1: **{metrics['macro_f1']:.6%}**",
        f"- Critical predictions mapped to High: **{metrics['critical_mapped_to_high']}**",
        f"- AI fallback responses: **{metrics['fallback_count']}**",
        "",
        "| Actual \\ Predicted | Low | Medium | High |",
        "|---|---:|---:|---:|",
    ]
    for actual in LABELS:
        row = metrics["confusion_matrix"][actual]
        lines.append(
            f"| {actual.title()} | {row['low']} | {row['medium']} | {row['high']} |"
        )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/kaggle-priority-benchmark")
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output_dir / "predictions.jsonl"
    completed = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            completed[str(record["ticket_id"])] = record
    with args.csv.open(encoding="utf-8-sig", newline="") as handle:
        sample = stratified_sample(list(csv.DictReader(handle)), args.seed)
    pending = [row for row in sample if row["ticket_id"] not in completed]
    print(
        f"Selected 200 rows; resuming with {len(completed)} complete and {len(pending)} pending."
    )
    for index, row in enumerate(pending, 1):
        title, description = ticket_text(row)
        result = classify_ticket(title, description)
        record = {
            "ticket_id": row["ticket_id"],
            "actual": row["priority"].lower(),
            "raw_prediction": result.priority,
            "predicted": normalize_prediction(result.priority),
            "department": result.department,
            "confidence": result.confidence,
            "fallback": result.confidence == 0.0,
        }
        with checkpoint.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        completed[row["ticket_id"]] = record
        if index % 10 == 0 or index == len(pending):
            print(
                f"Completed {len(completed)}/200; predictions={dict(Counter(item['predicted'] for item in completed.values()))}"
            )
    records = [completed[row["ticket_id"]] for row in sample]
    metrics = calculate_metrics(records)
    (args.output_dir / "results.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    write_report(metrics, args.output_dir / "summary.md")
    print((args.output_dir / "summary.md").read_text(encoding="utf-8"))
    return 0 if metrics["fallback_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
