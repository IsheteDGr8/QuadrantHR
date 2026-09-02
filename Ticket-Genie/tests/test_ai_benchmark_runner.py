from scripts.run_ai_benchmarks import DEFAULT_THRESHOLDS, markdown_report, score


def test_benchmark_metrics_and_failure_reporting():
    data = {
        "refusal": [{"id": "r", "expected_refusal": True, "predicted_refusal": True}],
        "routing": [{"id": "route", "expected": "IT", "predicted": "IT"}],
        "retrieval": [{"id": "ret", "relevant": ["d1"], "ranked": ["d1"]}],
        "grounded_answers": [
            {"id": "g", "context": "VPN requires MFA", "answer": "VPN requires MFA"}
        ],
        "answers": [
            {
                "id": "a",
                "answer": "Submit within 30 days",
                "required_terms": ["30 days"],
            }
        ],
    }
    metrics, failures = score(data)
    assert all(metrics[name] >= gate for name, gate in DEFAULT_THRESHOLDS.items())
    assert not any(failures.values())


def test_benchmark_detects_bad_predictions():
    data = {
        "refusal": [{"id": "r", "expected_refusal": True, "predicted_refusal": False}],
        "routing": [{"id": "route", "expected": "HR", "predicted": "IT"}],
        "retrieval": [{"id": "ret", "relevant": ["d1"], "ranked": ["d2"]}],
        "grounded_answers": [
            {"id": "g", "context": "five PTO days", "answer": "ten vacation days"}
        ],
        "answers": [
            {"id": "a", "answer": "Submit soon", "required_terms": ["30 days"]}
        ],
    }
    metrics, failures = score(data)
    assert all(metrics[name] < gate for name, gate in DEFAULT_THRESHOLDS.items())
    assert all(failures[name] for name in DEFAULT_THRESHOLDS)


def test_report_displays_macro_average():
    metrics = {name: 0.97 for name in DEFAULT_THRESHOLDS}
    report = markdown_report(metrics, {name: [] for name in DEFAULT_THRESHOLDS})
    assert "Overall macro-average: 97.0%" in report
