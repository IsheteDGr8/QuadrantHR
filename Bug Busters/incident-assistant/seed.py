"""Seeds the local database with sample policies so POST /incident can be
tested end-to-end without needing the frontend.

Run manually:

    python seed.py
"""

from database import Base, SessionLocal, engine
from models import Policy

SAMPLE_POLICIES = [
    {
        "name": "Workplace Harassment Policy",
        "description": "Prohibits harassment, bullying, and intimidation of any employee based on protected characteristics or otherwise, and outlines the reporting and investigation process.",
        "category": "Conduct",
        "related_keywords": "harassment, bullying, intimidation, hostile, discrimination, offensive comments, unwanted contact",
    },
    {
        "name": "Data Security & Confidentiality Policy",
        "description": "Governs how employees handle confidential company and customer data, including acceptable use of devices, credentials, and reporting of suspected breaches.",
        "category": "Security",
        "related_keywords": "data breach, leak, password, phishing, unauthorized access, confidential, malware, lost laptop",
    },
    {
        "name": "Workplace Safety Policy",
        "description": "Sets requirements for maintaining a safe physical work environment and the process for reporting injuries, hazards, and near-misses.",
        "category": "Safety",
        "related_keywords": "injury, accident, hazard, unsafe, fire, evacuation, equipment malfunction, near miss",
    },
    {
        "name": "Attendance & Punctuality Policy",
        "description": "Defines expectations for attendance, punctuality, and the process for reporting absences or tardiness.",
        "category": "Attendance",
        "related_keywords": "absent, late, tardy, no call no show, missed shift, sick day",
    },
    {
        "name": "Expense Reimbursement Policy",
        "description": "Outlines what business expenses are reimbursable and the process for submitting and approving expense claims.",
        "category": "Finance",
        "related_keywords": "expense, reimbursement, receipt, mileage, travel cost, overspending, fraud",
    },
    {
        "name": "Conflict of Interest Policy",
        "description": "Requires employees to disclose situations where personal interests could conflict with their duties to the company.",
        "category": "Conduct",
        "related_keywords": "conflict of interest, vendor relationship, side business, family member hired, gift, bribe",
    },
]


def main() -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        existing_count = db.query(Policy).count()

        if existing_count > 0:
            print(f"Policies table already has {existing_count} rows — skipping seed.")
            return

        for policy_data in SAMPLE_POLICIES:
            db.add(Policy(**policy_data))

        db.commit()
        print(f"Seeded {len(SAMPLE_POLICIES)} policies.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
