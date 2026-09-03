"""Idempotently upload the reviewed enterprise policy starter pack."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from fastapi import UploadFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services.knowledge_ingestion_service import ingest_document  # noqa: E402

TITLES = {
    "employee_benefits_and_insurance.md": "Employee Benefits and Insurance Policy",
    "paid_time_off_and_vacation.md": "Paid Time Off and Vacation Policy",
    "sick_safe_and_family_leave.md": "Sick, Safe, Family, and Parental Leave Policy",
    "retirement_and_financial_wellness.md": "Retirement and Financial Wellness Policy",
    "wellness_and_employee_assistance.md": "Wellness and Employee Assistance Program Policy",
    "equal_employment_anti_discrimination.md": "Equal Employment, Anti-Discrimination, and Anti-Harassment Policy",
    "workplace_accommodations.md": "Disability, Pregnancy, and Religious Accommodation Policy",
    "remote_work_and_information_security.md": "Remote Work and Information Security Policy",
    "code_of_conduct_and_ethics.md": "Code of Conduct, Ethics, and Speak-Up Policy",
    "travel_expense_and_reimbursement.md": "Business Travel, Expense, and Reimbursement Policy",
}


async def main() -> None:
    seed_dir = ROOT / "knowledge_seed"
    for filename, title in TITLES.items():
        path = seed_dir / filename
        with path.open("rb") as stream:
            result = await ingest_document(
                UploadFile(filename=filename, file=stream),
                title=title,
                category="General",
                uploaded_by={
                    "oid": "ticketgenie-policy-bootstrap",
                    "email": "deployment@ticketgenie.internal",
                },
            )
        print(f"{result['status']}: {title} ({result['id']})")


if __name__ == "__main__":
    asyncio.run(main())
