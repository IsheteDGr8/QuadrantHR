import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models_db import Base, TicketDB
from services.department_analytics_service import (
    AnalyticsAccessError,
    get_department_health_analytics,
    normalize_department,
    resolve_analytics_department,
)
from services.synthetic_ticket_service import (
    ensure_synthetic_tickets,
    seed_synthetic_tickets,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_synthetic_seed_is_reproducible_and_replaceable():
    db = make_session()
    result = seed_synthetic_tickets(db, count=360)
    assert result["created"] == 360
    assert db.query(TicketDB).filter(TicketDB.is_synthetic.is_(True)).count() == 360

    real_ticket = TicketDB(
        id="HD-REAL-1",
        title="Real ticket remains",
        category="IT Support",
        priority="Medium",
        status="Open",
        department="IT Team",
        description="This represents a real company ticket record.",
        date="2026-08-19",
        createdAt="2026-08-19T09:00:00",
        is_synthetic=False,
    )
    db.add(real_ticket)
    db.commit()

    seed_synthetic_tickets(db, count=120)
    assert db.query(TicketDB).filter(TicketDB.is_synthetic.is_(True)).count() == 120
    assert db.get(TicketDB, "HD-REAL-1") is not None


def test_synthetic_bootstrap_does_not_reseed_existing_data():
    db = make_session()
    first = ensure_synthetic_tickets(db, count=80)
    second = ensure_synthetic_tickets(db, count=80)

    assert first["created"] == 80
    assert second == {"created": 0, "existing": 80, "status": "already_seeded"}
    assert db.query(TicketDB).count() == 80


def test_department_health_is_calculated_from_scoped_tickets():
    db = make_session()
    seed_synthetic_tickets(db, count=360)

    result = get_department_health_analytics(db, "IT Team")

    assert result["department"] == "IT Team"
    assert result["data_mode"] == "synthetic"
    assert result["record_count"] > 80
    assert 0 <= result["kpis"]["health_score"] <= 100
    assert 0 <= result["kpis"]["sla_compliance_pct"] <= 100
    assert len(result["ticket_trends"]) == 12
    assert result["attention_queue"]
    assert all(item["department"] == "IT Team" for item in result["attention_queue"])
    assert result["brief"]["recommendations"]


def test_department_aliases_map_portal_names_to_ticket_departments():
    assert normalize_department("IT Operations") == "IT Team"
    assert normalize_department("Upper Executive Management") == "Upper Management"
    assert normalize_department("HR Team") == "HR Team"


def test_department_analytics_scope_comes_from_verified_identity():
    admin = {"role": "Admin", "department": "IT Operations"}
    assert resolve_analytics_department(admin, None) == "IT Team"
    assert resolve_analytics_department(admin, "IT Team") == "IT Team"

    with pytest.raises(AnalyticsAccessError):
        resolve_analytics_department(admin, "HR Team")

    with pytest.raises(AnalyticsAccessError):
        resolve_analytics_department(
            {"role": "Employee", "department": "IT Operations"}, None
        )

    ticketer = {"role": "Ticketer", "department": "HR Team"}
    assert resolve_analytics_department(ticketer, None) == "HR Team"
    with pytest.raises(AnalyticsAccessError):
        resolve_analytics_department(ticketer, "IT Team")
    with pytest.raises(AnalyticsAccessError):
        resolve_analytics_department({"role": "Ticketer"}, None)

    assert (
        resolve_analytics_department(
            {"role": "Super Admin", "department": "Upper Executive Management"},
            "HR Team",
        )
        == "HR Team"
    )
