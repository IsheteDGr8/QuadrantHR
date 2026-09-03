from scripts.run_kaggle_priority_benchmark import (
    calculate_metrics,
    normalize_prediction,
    ticket_text,
)


def test_kaggle_row_is_converted_to_ticket_text():
    row = {
        "product_area": "data_pipeline",
        "company_size": "Large",
        "industry": "finance",
        "region": "EMEA",
        "booking_channel": "chat",
        "customer_tier": "Enterprise",
        "customers_affected": "200",
        "error_rate_pct": "80",
        "downtime_min": "45",
        "payment_impact_flag": "1",
        "security_incident_flag": "0",
        "data_loss_flag": "0",
        "past_30d_tickets": "12",
        "past_90d_incidents": "3",
        "customer_sentiment": "negative",
    }
    title, description = ticket_text(row)
    assert title == "Data Pipeline support incident"
    assert "Affected users: 200" in description
    assert "downtime: 45 minutes" in description


def test_critical_is_normalized_to_kaggle_high():
    assert normalize_prediction("Critical") == "high"
    assert normalize_prediction("Medium") == "medium"


def test_metrics_include_accuracy_and_confusion_matrix():
    records = [
        {
            "actual": "low",
            "predicted": "low",
            "raw_prediction": "Low",
            "fallback": False,
        },
        {
            "actual": "medium",
            "predicted": "high",
            "raw_prediction": "High",
            "fallback": False,
        },
        {
            "actual": "high",
            "predicted": "high",
            "raw_prediction": "Critical",
            "fallback": False,
        },
    ]
    metrics = calculate_metrics(records)
    assert metrics["accuracy"] == 2 / 3
    assert metrics["successful_model_responses"] == 3
    assert metrics["model_response_accuracy"] == 2 / 3
    assert metrics["confusion_matrix"]["medium"]["high"] == 1
    assert metrics["critical_mapped_to_high"] == 1
