import sys
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import Policy
import main
from main import app

# StaticPool forces every connection through the same single SQLite
# in-memory connection — without it, each new session gets its own fresh
# (schema-less) in-memory database.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestSessionLocal()
    db.add(
        Policy(
            name="Data Security Policy",
            description="Governs data handling.",
            category="Security",
            related_keywords="data breach, leak, password, phishing",
        )
    )
    db.commit()
    db.close()

    yield


# --------------------------------------------------
# POST /incident
# --------------------------------------------------

@patch("main.agent.generate_follow_up_question")
def test_incident_with_match_creates_pending_review_ticket(mock_generate):
    mock_generate.return_value = "Was any customer data affected by this breach?"

    response = client.post(
        "/incident",
        json={"incident_text": "There was a data breach — someone leaked customer records."},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "pending_review"
    assert data["matched_policy_name"] == "Data Security Policy"
    assert data["follow_up_question"] == "Was any customer data affected by this breach?"
    assert data["error_message"] is None
    assert isinstance(data["ticket_id"], int)

    mock_generate.assert_called_once()


def test_incident_with_no_match_returns_no_match_status():
    response = client.post(
        "/incident",
        json={"incident_text": "The office coffee machine is broken."},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "no_match"
    assert data["matched_policy_name"] is None
    assert data["follow_up_question"] is None


@patch("main.agent.generate_follow_up_question")
def test_incident_with_agent_failure_returns_error_status(mock_generate):
    from agent import AgentError

    mock_generate.side_effect = AgentError("LLM call failed: service unavailable")

    response = client.post(
        "/incident",
        json={"incident_text": "There was a data breach — someone leaked customer records."},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "error"
    assert data["error_message"] is not None
    assert data["follow_up_question"] is None


def test_incident_with_blank_text_returns_400():
    response = client.post("/incident", json={"incident_text": "   "})

    assert response.status_code == 400


def test_incident_with_missing_field_returns_400():
    response = client.post("/incident", json={})

    assert response.status_code == 400


# --------------------------------------------------
# POST /ticket/:id/submit
# --------------------------------------------------

@patch("main.agent.generate_follow_up_question")
def test_submit_ticket_marks_as_submitted(mock_generate):
    mock_generate.return_value = "Was any customer data affected?"

    create_response = client.post(
        "/incident",
        json={"incident_text": "There was a data breach — someone leaked customer records."},
    )
    ticket_id = create_response.json()["ticket_id"]

    submit_response = client.post(
        f"/ticket/{ticket_id}/submit",
        json={"answer": "Yes, customer emails were exposed.", "confirmed": True},
    )

    assert submit_response.status_code == 200

    data = submit_response.json()

    assert data["status"] == "submitted"
    assert data["ticket_id"] == ticket_id

    fetched = client.get(f"/ticket/{ticket_id}")
    assert fetched.json()["status"] == "submitted"
    assert fetched.json()["answer"] == "Yes, customer emails were exposed."


def test_submit_ticket_not_found_returns_404():
    response = client.post(
        "/ticket/99999/submit",
        json={"answer": "Some answer", "confirmed": True},
    )

    assert response.status_code == 404


def test_submit_ticket_without_confirmation_returns_400():
    no_match_response = client.post(
        "/incident",
        json={"incident_text": "The office coffee machine is broken."},
    )
    ticket_id = no_match_response.json()["ticket_id"]

    response = client.post(
        f"/ticket/{ticket_id}/submit",
        json={"answer": "Some answer", "confirmed": False},
    )

    assert response.status_code == 400
