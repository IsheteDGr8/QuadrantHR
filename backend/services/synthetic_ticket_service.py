"""Deterministic synthetic ticket data for analytics demonstrations."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from database.models_db import TicketDB

DEPARTMENT_SCENARIOS = {
    "IT Team": [
        ("Identity & Access", "MFA reset loop after device replacement"),
        ("Network & VPN", "Intermittent VPN disconnect on remote network"),
        ("Email & Collaboration", "Shared mailbox permissions not updating"),
        ("Hardware", "Laptop battery health requires replacement"),
        ("Software Access", "Application license assignment is pending"),
    ],
    "HR Team": [
        ("Benefits", "Benefits enrollment selection needs correction"),
        ("Payroll", "Payroll deduction does not match employee election"),
        ("Employee Relations", "Manager guidance requested for team concern"),
        ("Leave Management", "Leave balance and accrual need review"),
        ("Onboarding", "New hire onboarding task is blocked"),
    ],
    "Accounting Team": [
        ("Expense Reimbursement", "Expense report awaiting reimbursement review"),
        ("Accounts Payable", "Vendor invoice approval is delayed"),
        ("Corporate Card", "Corporate card transaction requires reconciliation"),
        ("Budget Access", "Cost center budget access is missing"),
        ("Travel", "Travel expense receipt exception needs approval"),
    ],
    "Workplace Operations Team": [
        ("Facilities", "Office temperature issue reported on third floor"),
        ("Badge Access", "Building badge access stopped working"),
        ("Equipment", "Conference room equipment is unavailable"),
        ("Safety", "Workplace safety inspection follow-up required"),
        ("Workspace", "Desk reservation conflict needs resolution"),
    ],
    "Upper Management": [
        ("Approval", "Cross-department exception requires executive approval"),
        ("Compliance", "Policy exception needs governance review"),
        ("Escalation", "Customer-impacting issue requires escalation decision"),
        ("Leave Management", "Extended leave request awaits final approval"),
        ("Risk", "Operational risk acceptance requires leadership review"),
    ],
}

DEPARTMENT_WEIGHTS = {
    "IT Team": 0.38,
    "HR Team": 0.22,
    "Accounting Team": 0.16,
    "Workplace Operations Team": 0.16,
    "Upper Management": 0.08,
}

SLA_HOURS = {"Critical": 4, "High": 8, "Medium": 24, "Low": 72}


def seed_synthetic_tickets(
    db: Session,
    count: int = 360,
    replace: bool = True,
    seed: int = 20260819,
) -> dict:
    """Create a reproducible 90-day dataset without touching real tickets."""
    if count < 50 or count > 5000:
        raise ValueError("Synthetic ticket count must be between 50 and 5000.")

    if replace:
        db.query(TicketDB).filter(TicketDB.is_synthetic.is_(True)).delete()

    rng = random.Random(seed)
    now = datetime.now().replace(microsecond=0)
    departments = list(DEPARTMENT_WEIGHTS)
    weights = list(DEPARTMENT_WEIGHTS.values())
    records = []

    for index in range(1, count + 1):
        age_days = int((rng.random() ** 1.25) * 90)
        created = now - timedelta(
            days=age_days,
            hours=rng.randint(0, 20),
            minutes=rng.randint(0, 59),
        )
        department = rng.choices(departments, weights=weights, k=1)[0]
        scenarios = DEPARTMENT_SCENARIOS[department]

        # Deliberately create recent issue clusters so emerging-issue analytics
        # has realistic signals instead of uniformly random noise.
        if department == "IT Team" and age_days <= 14 and rng.random() < 0.42:
            category, title = scenarios[rng.choice([0, 1])]
        elif department == "HR Team" and age_days <= 14 and rng.random() < 0.30:
            category, title = scenarios[1]
        else:
            category, title = rng.choice(scenarios)

        priority = rng.choices(
            ["Low", "Medium", "High", "Critical"],
            weights=[0.16, 0.54, 0.24, 0.06],
            k=1,
        )[0]
        open_probability = 0.30 if age_days <= 14 else 0.12 if age_days <= 30 else 0.03
        is_open = rng.random() < open_probability
        status = (
            rng.choice(["Open", "In Progress", "Pending"]) if is_open else "Resolved"
        )

        updated = None
        if not is_open:
            target = SLA_HOURS[priority]
            resolution_hours = max(0.5, rng.lognormvariate(1.15, 0.65))
            if rng.random() < 0.14:
                resolution_hours += target * rng.uniform(1.05, 2.4)
            updated = min(now, created + timedelta(hours=resolution_hours))
        elif status == "In Progress":
            updated = min(now, created + timedelta(hours=rng.uniform(1, 18)))

        confidence = round(rng.uniform(0.72, 0.99), 2)
        needs_review = confidence < 0.80 or (
            priority == "Critical" and rng.random() < 0.2
        )
        requester = f"synthetic.employee{rng.randint(1, 85):03d}@ticketgenie.test"
        records.append(
            TicketDB(
                id=f"SYN-{index:05d}",
                title=title,
                category=category,
                priority=priority,
                status=status,
                department=department,
                queue=f"{department} Queue",
                description=(
                    f"Synthetic analytics scenario: {title.lower()}. "
                    "The employee supplied reproducible details for operational triage."
                ),
                date=created.date().isoformat(),
                createdAt=created.isoformat(),
                updatedAt=updated.isoformat() if updated else None,
                requester_id=requester,
                classification_status="Classified",
                classification_confidence=str(confidence),
                classification_reason=(
                    f"Synthetic classifier routed this {category} request to {department}."
                ),
                needs_human_review=needs_review,
                model_deployment="synthetic-analytics-v1",
                auto_resolved=(not is_open and rng.random() < 0.24),
                is_synthetic=True,
            )
        )

    db.add_all(records)
    db.commit()
    return {
        "created": len(records),
        "replaced_existing_synthetic": replace,
        "seed": seed,
        "date_range_days": 90,
    }


def ensure_synthetic_tickets(db: Session, count: int = 360) -> dict:
    """Seed demo analytics once; preserve both existing synthetic and real data."""
    existing = db.query(TicketDB).filter(TicketDB.is_synthetic.is_(True)).count()
    if existing:
        return {"created": 0, "existing": existing, "status": "already_seeded"}
    result = seed_synthetic_tickets(db, count=count, replace=False)
    return {**result, "status": "seeded"}
