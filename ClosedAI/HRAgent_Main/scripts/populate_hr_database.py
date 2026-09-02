"""
Populate the closedai-hr Cosmos database with interconnected seed data.

Designed for a shared-throughput database capped at 1000 RU/s (autoscale,
which floors at ~100 RU/s until it scales up). Writes will not crash the
run on throttle:

  * Cosmos SDK retries 429s internally (retry_throttle_total=30).
  * An adaptive token-bucket caps write RU/s, starting ~70 RU/s (under the
    autoscale floor) and ramping only while 429-free; halves on throttle.
  * Application-level retry on 429/408/449/503 using x-ms-retry-after-ms.
  * Sequential upserts (idempotent) so a re-run is safe.

Usage:
  python HRAgent_Main/scripts/populate_hr_database.py --dry-run
  python HRAgent_Main/scripts/populate_hr_database.py
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Unbuffered progress when spawned without a TTY.
os.environ.setdefault("PYTHONUNBUFFERED", "1")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from hr_database_schema import (  # noqa: E402
    COMPANY,
    DATABASE_NAME,
    SCHEMA_VERSION,
    entity_to_container,
    population_order,
)

AS_OF = date(2026, 8, 19)
AS_OF_ISO = "2026-08-19"
NOW_Z = "2026-08-19T18:00:00Z"
N_EMPLOYEES = 200

FIRST = [
    "Ava", "Liam", "Mia", "Noah", "Priya", "Diego", "Sofia", "Kai", "Elena", "Jamal",
    "Hannah", "Owen", "Zara", "Theo", "Amara", "Leo", "Nina", "Marcus", "Chloe", "Ryan",
    "Aisha", "Ben", "Lucia", "Ethan", "Mei", "Jordan", "Camila", "Alex", "Sara", "Mateo",
    "Ivy", "Sam", "Leila", "Chris", "Anya", "Victor", "Grace", "Omar", "Ruby", "Daniel",
    "Naomi", "Hugo", "Iris", "Felix", "Tara", "Miles", "Quinn", "Nadia", "Cole", "Yuna",
]
LAST = [
    "Chen", "Patel", "Nguyen", "Garcia", "Kim", "Johnson", "Nair", "Moore", "Singh", "Brown",
    "Martinez", "Lee", "Khan", "Wilson", "Park", "Rivera", "Shah", "Clark", "Ali", "Wright",
    "Hernandez", "Lopez", "Walker", "Young", "Scott", "Green", "Adams", "Baker", "Nelson", "Carter",
    "Mitchell", "Perez", "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins",
]

FAMILIES = [
    ("family-eng", "ENG", "Engineering"),
    ("family-prod", "PROD", "Product"),
    ("family-data", "DATA", "Data"),
    ("family-design", "DESIGN", "Design"),
    ("family-sales", "SALES", "Sales"),
    ("family-cs", "CS", "Customer Success"),
    ("family-mkt", "MKT", "Marketing"),
    ("family-fin", "FIN", "Finance"),
    ("family-people", "PEOPLE", "People"),
    ("family-ops", "OPS", "Operations"),
]

DEPT_META = [
    # id, name, family, target headcount (approx)
    ("dept-eng", "Engineering", "ENG", 48),
    ("dept-product", "Product", "PROD", 18),
    ("dept-data", "Data", "DATA", 16),
    ("dept-design", "Design", "DESIGN", 10),
    ("dept-sales", "Sales", "SALES", 20),
    ("dept-cs", "Customer Success", "CS", 16),
    ("dept-mkt", "Marketing", "MKT", 10),
    ("dept-fin", "Finance", "FIN", 12),
    ("dept-people", "People", "PEOPLE", 14),
    ("dept-ops", "Operations", "OPS", 16),
]

LEVEL_TITLES = {
    "ENG": {1: "Software Engineer I", 2: "Software Engineer II", 3: "Senior Software Engineer",
            4: "Staff Software Engineer", 5: "Engineering Manager", 6: "Director of Engineering",
            7: "VP of Engineering"},
    "PROD": {1: "APM", 2: "Product Manager", 3: "Senior Product Manager", 4: "Principal PM",
             5: "Group Product Manager", 6: "Director of Product", 7: "Chief Product Officer"},
    "DATA": {1: "Data Analyst", 2: "Data Scientist", 3: "Senior Data Scientist", 4: "Staff Data Scientist",
             5: "Data Science Manager", 6: "Director of Data", 7: "VP of Data"},
    "DESIGN": {1: "Designer I", 2: "Product Designer", 3: "Senior Product Designer", 4: "Staff Designer",
               5: "Design Manager", 6: "Director of Design", 7: "VP of Design"},
    "SALES": {1: "SDR", 2: "Account Executive", 3: "Senior AE", 4: "Enterprise AE",
              5: "Sales Manager", 6: "Director of Sales", 7: "Chief Revenue Officer"},
    "CS": {1: "Support Specialist", 2: "CSM", 3: "Senior CSM", 4: "Staff CSM",
           5: "CS Manager", 6: "Director of CS", 7: "VP of Customer Success"},
    "MKT": {1: "Marketing Coordinator", 2: "Marketing Manager", 3: "Senior Marketing Manager",
            4: "Growth Lead", 5: "Marketing Manager II", 6: "Director of Marketing", 7: "CMO"},
    "FIN": {1: "Staff Accountant", 2: "Financial Analyst", 3: "Senior Analyst", 4: "Finance Lead",
            5: "Finance Manager", 6: "Director of Finance", 7: "CFO"},
    "PEOPLE": {1: "HR Coordinator", 2: "HR Generalist", 3: "Senior HRBP", 4: "Staff HRBP",
               5: "People Manager", 6: "Director of People", 7: "CHRO"},
    "OPS": {1: "Ops Associate", 2: "Ops Specialist", 3: "Senior Ops Specialist", 4: "Ops Lead",
            5: "Ops Manager", 6: "Director of Operations", 7: "COO"},
}

BAND_MID = {
    1: 85000, 2: 110000, 3: 145000, 4: 175000,
    5: 190000, 6: 220000, 7: 280000, 8: 420000,
}

SKILL_CATALOG = [
    ("skill-python", "Python", "Engineering", "technical"),
    ("skill-java", "Java", "Engineering", "technical"),
    ("skill-sql", "SQL", "Data", "technical"),
    ("skill-product-strategy", "Product Strategy", "Product", "functional"),
    ("skill-roadmapping", "Roadmapping", "Product", "functional"),
    ("skill-leadership", "Leadership", "Leadership", "leadership"),
    ("skill-communication", "Communication", "Leadership", "leadership"),
    ("skill-security-awareness", "Security Awareness", "Security", "functional"),
    ("skill-sales", "Consultative Selling", "Sales", "functional"),
    ("skill-design-systems", "Design Systems", "Design", "functional"),
    ("skill-payroll", "Payroll Operations", "People", "functional"),
    ("skill-coaching", "Coaching", "Leadership", "leadership"),
]


# ---------------------------------------------------------------------------
# Adaptive, throttle-safe Cosmos writer
# ---------------------------------------------------------------------------
class AdaptiveWriter:
    """Sequential upserts that stay under shared autoscale throughput.

    Autoscale-1000 floors at ~100 RU/s until Cosmos scales up, so we start
    well below that and only speed up after a streak of non-throttled writes.
    """

    def __init__(self, db_client: Any, start_ru_s: float = 70.0, max_ru_s: float = 420.0) -> None:
        self.db = db_client
        self.target_ru_s = start_ru_s
        self.max_ru_s = max_ru_s
        self.min_ru_s = 45.0
        self.window: list[tuple[float, float]] = []
        self.success_streak = 0
        self.throttle_count = 0
        self.written = 0
        self._containers: dict[str, Any] = {}
        self._mapping = entity_to_container()

    def container(self, physical: str) -> Any:
        if physical not in self._containers:
            self._containers[physical] = self.db.get_container_client(physical)
        return self._containers[physical]

    def _ru_last_second(self) -> float:
        now = time.monotonic()
        self.window = [(t, r) for t, r in self.window if now - t < 1.0]
        return sum(r for _, r in self.window)

    def _wait_for_budget(self, estimated: float = 8.0) -> None:
        while self._ru_last_second() + estimated > self.target_ru_s:
            time.sleep(0.04)

    def upsert(self, entity: str, doc: dict[str, Any]) -> None:
        physical = self._mapping[entity]
        client = self.container(physical)
        last_err: Exception | None = None
        for attempt in range(40):
            self._wait_for_budget()
            charge = [8.0]

            def hook(headers: Any, _body: Any = None) -> None:
                try:
                    charge[0] = float(headers.get("x-ms-request-charge") or 8.0)
                except (TypeError, ValueError):
                    charge[0] = 8.0

            try:
                client.upsert_item(doc, response_hook=hook)
                self.window.append((time.monotonic(), charge[0]))
                self.written += 1
                self.success_streak += 1
                if self.success_streak % 30 == 0:
                    self.target_ru_s = min(self.max_ru_s, self.target_ru_s + 20.0)
                return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                status = getattr(exc, "status_code", None)
                if status == 429:
                    self.throttle_count += 1
                    self.success_streak = 0
                    self.target_ru_s = max(self.min_ru_s, self.target_ru_s * 0.5)
                    wait_s = _retry_after_seconds(exc, fallback=1.0)
                    time.sleep(wait_s + random.uniform(0.05, 0.25))
                    continue
                if status in (408, 449, 503) or _is_transient(exc):
                    time.sleep(min(2 ** min(attempt, 5), 20) + random.uniform(0, 0.4))
                    continue
                raise
        raise RuntimeError(f"Gave up upserting {entity} {doc.get('id')} after 40 attempts: {last_err}")


def _retry_after_seconds(exc: Exception, fallback: float) -> float:
    headers = getattr(exc, "headers", None) or {}
    ms = headers.get("x-ms-retry-after-ms") or headers.get("Retry-After")
    try:
        if ms is None:
            return fallback
        val = float(ms)
        return val / 1000.0 if val > 20 else val
    except (TypeError, ValueError):
        return fallback


def _is_transient(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(tok in text for tok in ("429", "timeout", "throttl", "gone", "503", "connection"))


def _stamp(entity: str, doc: dict[str, Any], created: str | None = None) -> dict[str, Any]:
    doc["recordType"] = entity
    doc["company"] = COMPANY
    doc["schemaVersion"] = SCHEMA_VERSION
    doc["createdAt"] = created or NOW_Z
    doc["updatedAt"] = NOW_Z
    return doc


def emp_id(n: int) -> str:
    return f"emp-{n:04d}"


def iso(d: date) -> str:
    return d.isoformat()


def tenure_years(hire: date, end: date | None = None) -> float:
    end = end or AS_OF
    return round(max((end - hire).days, 0) / 365.25, 1)


def pto_accrual(years: float) -> int:
    if years < 2:
        return 15
    if years < 5:
        return 18
    return 22


def business_days(start: date, end: date) -> int:
    n = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return max(n, 1)


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in (HERE / ".." / ".." / ".env", HERE / ".." / ".env", Path.cwd() / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return


# ---------------------------------------------------------------------------
# World generation
# ---------------------------------------------------------------------------
def generate(rng: random.Random) -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # ---- catalogs ----
    for fid, code, name in FAMILIES:
        data["job_families"].append(_stamp("job_families", {
            "id": fid, "jobFamilyId": fid, "code": code, "name": name,
            "description": f"{name} job family.",
        }))

    locations = [
        ("loc-sea", "Seattle HQ", "office", "500 Pike St", "Seattle", "WA", "US",
         "America/Los_Angeles", True),
        ("loc-sf", "San Francisco", "office", "100 Market St", "San Francisco", "CA", "US",
         "America/Los_Angeles", False),
        ("loc-nyc", "New York", "office", "200 Park Ave", "New York", "NY", "US",
         "America/New_York", False),
        ("loc-austin", "Austin", "office", "600 Congress", "Austin", "TX", "US",
         "America/Chicago", False),
        ("loc-london", "London", "office", "1 Canada Square", "London", None, "GB",
         "Europe/London", False),
        ("loc-remote-us", "Remote US", "remote", None, None, None, "US",
         "America/Los_Angeles", False),
    ]
    for row in locations:
        lid, name, typ, addr, city, state, country, tz, hq = row
        data["locations"].append(_stamp("locations", {
            "id": lid, "locationId": lid, "name": name, "type": typ,
            "addressLine": addr, "city": city, "state": state, "country": country,
            "timezone": tz, "isHeadquarters": hq,
        }))

    for sid, sname, cat, stype in SKILL_CATALOG:
        data["skills_taxonomy"].append(_stamp("skills_taxonomy", {
            "id": sid, "skillId": sid, "name": sname, "category": cat,
            "taxonomyPath": f"{cat}/{sname}",
            "proficiencyLevels": ["novice", "intermediate", "advanced", "expert"],
            "type": stype,
        }))

    data["leave_policies"].append(_stamp("leave_policies", {
        "id": "lp-pto", "leavePolicyId": "lp-pto", "leaveType": "pto",
        "accrualRule": "15 days (<2y), 18 (2-5y), 22 (5y+)",
        "accrualTiers": [
            {"minTenureYears": 0, "maxTenureYears": 2, "daysPerYear": 15},
            {"minTenureYears": 2, "maxTenureYears": 5, "daysPerYear": 18},
            {"minTenureYears": 5, "maxTenureYears": 99, "daysPerYear": 22},
        ],
        "maxCarryoverDays": 5, "paid": True, "jurisdiction": "US", "policyId": "policy-pto",
    }))
    data["leave_policies"].append(_stamp("leave_policies", {
        "id": "lp-sick", "leavePolicyId": "lp-sick", "leaveType": "sick",
        "accrualRule": "10 days/year",
        "accrualTiers": [{"minTenureYears": 0, "maxTenureYears": 99, "daysPerYear": 10}],
        "maxCarryoverDays": 0, "paid": True, "jurisdiction": "US", "policyId": "policy-sick",
    }))

    plans = [
        ("plan-med-ppo", "PPO Plus", "medical", "BlueCross", 120, 300, 1000, 4000, 80),
        ("plan-med-hmo", "HMO Core", "medical", "Kaiser", 80, 200, 500, 3000, 85),
        ("plan-den-std", "Dental Standard", "dental", "Delta", 25, 45, None, None, 70),
        ("plan-vis-basic", "Vision Basic", "vision", "VSP", 12, 20, None, None, 70),
        ("plan-401k", "401(k)", "retirement_401k", "Fidelity", 0, 0, None, None, 100),
        ("plan-hsa", "HSA", "hsa", "HealthEquity", 0, 0, None, None, 100),
        ("plan-life", "Basic Life", "life", "MetLife", 8, 0, None, None, 100),
        ("plan-ltd", "Long-term Disability", "disability", "Unum", 15, 0, None, None, 100),
        ("plan-eap", "Employee Assistance", "eap", "Lyra", 0, 0, None, None, 100),
    ]
    for p in plans:
        pid, pname, ptype, carrier, prem, dep, ded, oop, contrib = p
        data["benefits_plans"].append(_stamp("benefits_plans", {
            "id": pid, "planId": pid, "planName": pname, "planType": ptype, "carrier": carrier,
            "monthlyPremiumEmployee": prem, "monthlyPremiumDependent": dep,
            "deductible": ded, "outOfPocketMax": oop,
            "companyContributionPercent": contrib, "currency": "USD",
            "eligibilityRule": "full_time",
        }))

    data["pay_groups"].append(_stamp("pay_groups", {
        "id": "pg-us-biweekly", "payGroupId": "pg-us-biweekly", "name": "US Biweekly",
        "frequency": "biweekly", "periodsPerYear": 26, "currency": "USD", "country": "US",
    }))
    data["pay_groups"].append(_stamp("pay_groups", {
        "id": "pg-us-monthly", "payGroupId": "pg-us-monthly", "name": "US Monthly Exec",
        "frequency": "monthly", "periodsPerYear": 12, "currency": "USD", "country": "US",
    }))

    templates = [
        ("tmpl-i9", "I-9 Employment Eligibility", "i9", "pdf"),
        ("tmpl-offer", "Offer Letter", "offer_letter", "docx"),
        ("tmpl-nda", "Employee NDA", "nda", "pdf"),
        ("tmpl-w4", "W-4", "w4", "pdf"),
        ("tmpl-handbook", "Handbook Acknowledgment", "handbook_ack", "docx"),
        ("tmpl-emergency", "Emergency Contact", "emergency_contact", "docx"),
        ("tmpl-review", "Performance Review", "performance_review", "docx"),
        ("tmpl-sep", "Separation Agreement", "separation_agreement", "docx"),
    ]
    for tid, tname, ttype, fmt in templates:
        data["document_templates"].append(_stamp("document_templates", {
            "id": tid, "templateId": tid, "name": tname, "type": ttype, "format": fmt,
            "storageUrl": f"workspace://{tid}.{fmt}",
            "fields": ["employee_name", "employee_id", "start_date"],
        }))

    vendors = [
        ("vendor-checkr", "Checkr", "background_check"),
        ("vendor-adp", "ADP", "payroll"),
        ("vendor-greenhouse", "Greenhouse", "ats"),
        ("vendor-workday", "Workday", "hris"),
        ("vendor-deg", "Degreed", "lms"),
        ("vendor-alight", "Alight", "benefits_broker"),
        ("vendor-cultureamp", "Culture Amp", "engagement"),
        ("vendor-mercer", "Mercer", "consulting"),
    ]
    for vid, vname, vcat in vendors:
        data["vendors"].append(_stamp("vendors", {
            "id": vid, "vendorId": vid, "name": vname, "category": vcat,
            "contractStart": "2025-01-01", "contractEnd": "2026-12-31",
            "annualCost": rng.choice([12000, 24000, 48000, 90000]),
            "ownerId": emp_id(9), "status": "active",
        }))

    data["data_retention_schedules"].append(_stamp("data_retention_schedules", {
        "id": "ret-employee", "scheduleId": "ret-employee", "dataDomain": "core_hr",
        "retentionPeriodMonths": 84, "triggerEvent": "termination",
        "dispositionAction": "anonymize", "legalHoldEligible": True, "ownerId": emp_id(9),
    }))
    data["data_retention_schedules"].append(_stamp("data_retention_schedules", {
        "id": "ret-recruiting", "scheduleId": "ret-recruiting", "dataDomain": "talent",
        "retentionPeriodMonths": 24, "triggerEvent": "creation",
        "dispositionAction": "delete", "legalHoldEligible": True, "ownerId": emp_id(9),
    }))

    cycles = [
        ("cycle-2025-annual", "2025 Annual", "annual", "2025-11-01", "2025-12-15", "closed"),
        ("cycle-2026-h1", "2026 Mid-Year", "mid_year", "2026-06-01", "2026-06-30", "closed"),
        ("cycle-2026-annual", "2026 Annual", "annual", "2026-11-01", "2026-12-15", "active"),
    ]
    for cid, cname, ctype, sd, ed, st in cycles:
        data["review_cycles"].append(_stamp("review_cycles", {
            "id": cid, "cycleId": cid, "name": cname, "type": ctype,
            "startDate": sd, "endDate": ed, "status": st,
        }))

    data["surveys"].append(_stamp("surveys", {
        "id": "survey-2026-q2", "surveyId": "survey-2026-q2",
        "name": "Q2 2026 Engagement Pulse", "type": "engagement",
        "launchDate": "2026-04-15", "closeDate": "2026-04-30",
        "anonymous": True, "questionCount": 20, "participationRate": 0.82,
    }))
    data["surveys"].append(_stamp("surveys", {
        "id": "survey-2026-dei", "surveyId": "survey-2026-dei",
        "name": "2026 DEI Census", "type": "dei",
        "launchDate": "2026-03-01", "closeDate": "2026-03-21",
        "anonymous": True, "questionCount": 12, "participationRate": 0.71,
    }))

    courses = [
        ("course-sec-101", "Security Awareness 101", True),
        ("course-harassment", "Preventing Harassment", True),
        ("course-manager-101", "New Manager Essentials", False),
        ("course-ai-ethics", "Responsible AI in HR", False),
        ("course-payroll", "Payroll Foundations", False),
    ]
    for cid, title, mandatory in courses:
        data["learning_courses"].append(_stamp("learning_courses", {
            "id": cid, "courseId": cid, "title": title, "modality": "elearning",
            "durationHours": 1.0 if mandatory else 2.5, "mandatory": mandatory,
            "skillIdsCovered": ["skill-security-awareness"] if "sec" in cid else ["skill-leadership"],
            "provider": "Internal",
        }))

    reqs_comp = [
        ("req-comp-i9", "I-9", "Employment eligibility verification within 3 days of hire.", "per_event"),
        ("req-comp-eeo", "EEO", "Annual EEO-1 filing.", "annual"),
        ("req-comp-fmla", "FMLA", "Track FMLA eligibility and leave.", "ongoing"),
        ("req-comp-osha", "OSHA", "Workplace safety log.", "annual"),
        ("req-comp-gdpr", "GDPR", "Process DSARs within 30 days.", "per_event"),
        ("req-comp-ccpa", "CCPA", "Honor California privacy requests.", "per_event"),
        ("req-comp-aca", "ACA", "Offer compliant medical coverage.", "annual"),
    ]
    for rid, reg, desc, freq in reqs_comp:
        data["compliance_requirements"].append(_stamp("compliance_requirements", {
            "id": rid, "requirementId": rid, "regulation": reg, "description": desc,
            "jurisdiction": "US" if reg != "GDPR" else "EU", "frequency": freq,
            "ownerId": emp_id(9), "status": "compliant", "nextDueDate": "2026-12-31",
        }))

    # ---- jobs + bands ----
    job_by_family_level: dict[tuple[str, int], str] = {}
    jn = 1
    for _fid, code, _name in FAMILIES:
        for level in range(1, 8):
            jid = f"job-{jn:04d}"
            jn += 1
            title = LEVEL_TITLES[code][level]
            job_by_family_level[(code, level)] = jid
            data["jobs"].append(_stamp("jobs", {
                "id": jid, "jobId": jid, "title": title, "jobFamily": code, "level": level,
                "flsaStatus": "non_exempt" if level <= 1 and code in ("CS", "OPS", "FIN") else "exempt",
                "isManagerJob": level >= 5,
                "description": f"{title} in {code}.",
                "requiredSkillIds": [SKILL_CATALOG[0][0], "skill-communication"],
            }))
    data["jobs"].append(_stamp("jobs", {
        "id": "job-ceo", "jobId": "job-ceo", "title": "Chief Executive Officer",
        "jobFamily": "PEOPLE", "level": 8, "flsaStatus": "exempt", "isManagerJob": True,
        "description": "CEO.", "requiredSkillIds": ["skill-leadership"],
    }))
    job_by_family_level[("PEOPLE", 8)] = "job-ceo"

    for _fid, code, _name in FAMILIES:
        for level in range(1, 8):
            mid = BAND_MID[level]
            bid = f"band-{code}-{level}"
            data["compensation_bands"].append(_stamp("compensation_bands", {
                "id": bid, "bandId": bid, "jobFamily": code, "level": level,
                "currency": "USD", "min": int(mid * 0.82), "mid": mid, "max": int(mid * 1.18),
                "geoZone": "US-national",
            }))
    data["compensation_bands"].append(_stamp("compensation_bands", {
        "id": "band-PEOPLE-8", "bandId": "band-PEOPLE-8", "jobFamily": "PEOPLE", "level": 8,
        "currency": "USD", "min": 350000, "mid": 420000, "max": 500000, "geoZone": "US-national",
    }))

    data["data_governance_policies"].append(_stamp("data_governance_policies", {
        "id": "dgp-pii-access", "policyId": "dgp-pii-access", "title": "PII Access Control Policy",
        "domain": "access", "appliesToClassifications": ["pii", "sensitive_pii"],
        "rule": "Access to PII requires role-based approval + logged purpose.",
        "ownerId": emp_id(9), "effectiveDate": "2026-01-01", "reviewDate": "2027-01-01",
    }))
    data["data_governance_policies"].append(_stamp("data_governance_policies", {
        "id": "dgp-ai-use", "policyId": "dgp-ai-use", "title": "AI Use in HR Policy",
        "domain": "ai_use", "appliesToClassifications": ["confidential", "pii"],
        "rule": "High-risk AI systems require human-in-the-loop and annual bias audit.",
        "ownerId": emp_id(9), "effectiveDate": "2026-01-01", "reviewDate": "2027-01-01",
    }))

    # ---- employees (org tree) ----
    # Slot 1 CEO, 2-11 execs (one per dept), then directors/managers/ICs.
    exec_slots = [
        (2, "dept-eng", "ENG", 7, "Joseph", "Johnson"),
        (3, "dept-product", "PROD", 7, "Priya", "Nair"),
        (4, "dept-data", "DATA", 7, "Diego", "Moore"),
        (5, "dept-design", "DESIGN", 7, "Elena", "Garcia"),
        (6, "dept-sales", "SALES", 7, "Jamal", "Wright"),
        (7, "dept-cs", "CS", 7, "Sofia", "Martinez"),
        (8, "dept-mkt", "MKT", 7, "Kai", "Chen"),
        (9, "dept-people", "PEOPLE", 7, "Amara", "Patel"),
        (10, "dept-fin", "FIN", 7, "Owen", "Kim"),
        (11, "dept-ops", "OPS", 7, "Hannah", "Lee"),
    ]
    exec_by_dept = {d: emp_id(n) for n, d, *_ in exec_slots}

    people: list[dict[str, Any]] = []

    def add_person(n: int, first: str, last: str, dept: str, family: str, level: int,
                   manager: str | None, loc: str, hire: date, status: str = "active",
                   work_mode: str = "hybrid") -> dict[str, Any]:
        eid = emp_id(n)
        jid = job_by_family_level[(family, level)]
        title = "Chief Executive Officer" if level == 8 else LEVEL_TITLES[family][level]
        years = tenure_years(hire)
        mid = BAND_MID[level]
        salary = int(mid * rng.uniform(0.88, 1.08) / 1000) * 1000
        band_id = f"band-{family}-{level}"
        flsa = "non_exempt" if level <= 1 and family in ("CS", "OPS", "FIN") else "exempt"
        emp_type = "full_time"
        visa = "citizen"
        if rng.random() < 0.15:
            visa = rng.choice(["visa", "permanent_resident"])
        loc_name = next(x[1] for x in locations if x[0] == loc)
        dept_name = "ClosedAI" if dept == "dept-company" else next(d[1] for d in DEPT_META if d[0] == dept)
        pto_days = pto_accrual(years)
        used = rng.randint(2, min(8, pto_days - 2))
        remaining = pto_days - used
        person = {
            "id": eid, "employeeId": eid, "firstName": first, "lastName": last,
            "name": f"{first} {last}", "preferredName": first,
            "workEmail": f"{first.lower()}.{last.lower()}{n}@closedai.com",
            "personalEmail": f"{first.lower()}.{last.lower()}@gmail.com",
            "phone": f"+1-206-555-{1000 + n:04d}",
            "dateOfBirth": iso(date(rng.randint(1975, 1998), rng.randint(1, 12), rng.randint(1, 28))),
            "gender": rng.choice(["female", "male", "nonbinary", None]),
            "ethnicity": None,
            "employmentStatus": status, "employmentType": emp_type, "flsaStatus": flsa,
            "hireDate": iso(hire),
            "terminationDate": iso(hire + timedelta(days=rng.randint(400, 2000))) if status == "terminated" else None,
            "tenureYears": years, "departmentId": dept, "departmentName": dept_name,
            "jobId": jid, "jobTitle": title, "jobLevel": level, "positionId": f"pos-{n:04d}",
            "managerId": manager, "managerName": None,
            "isPeopleManager": False, "directReportCount": 0,
            "workLocationId": loc, "workLocationName": loc_name,
            "country": "US" if loc != "loc-london" else "GB",
            "workMode": work_mode, "timezone": next(x[7] for x in locations if x[0] == loc),
            "compensation": {
                "annualSalary": salary, "currency": "USD",
                "payFrequency": "monthly" if level >= 7 else "biweekly",
                "bandId": band_id, "compaRatio": round(salary / mid, 2),
            },
            "workAuthorization": {
                "status": visa,
                "visaType": "H-1B" if visa == "visa" else None,
                "expirationDate": "2027-06-01" if visa == "visa" else None,
            },
            "ptoSnapshot": {
                "accrualDaysPerYear": pto_days, "usedDays": used,
                "remainingDays": remaining, "asOf": AS_OF_ISO,
            },
            "benefitsSnapshot": {
                "medicalPlanId": "plan-med-ppo", "medicalPlanName": "PPO Plus",
                "dentalPlanId": "plan-den-std", "visionPlanId": "plan-vis-basic",
                "retirement401kPercent": 6, "employerMatchPercent": 4,
            },
            "engagementScore": round(rng.uniform(6.2, 8.8), 1),
            "lastSurveyDate": "2026-05-01",
            "attritionRiskScore": round(rng.uniform(0.05, 0.45), 2),
        }
        people.append(person)
        return person

    add_person(1, "Ava", "Chen", "dept-company", "PEOPLE", 8, None, "loc-sea",
               date(2018, 3, 1), work_mode="onsite")
    for n, dept, family, level, first, last in exec_slots:
        add_person(n, first, last, dept, family, level, emp_id(1),
                   rng.choice(["loc-sea", "loc-sf", "loc-nyc"]),
                   date(2018 + (n % 4), n % 12 + 1, 1 + (n % 20)))

    # Remaining headcount per dept (includes the exec already counted).
    remaining_slots: list[tuple[str, str]] = []
    for did, _n, family, target in DEPT_META:
        already = 1  # exec
        for _ in range(max(target - already, 0)):
            remaining_slots.append((did, family))
    # CEO is extra; trim/pad to exactly N_EMPLOYEES - 1 (CEO) - 10 execs
    needed = N_EMPLOYEES - 11
    if len(remaining_slots) > needed:
        remaining_slots = remaining_slots[:needed]
    while len(remaining_slots) < needed:
        remaining_slots.append(rng.choice([(d[0], d[2]) for d in DEPT_META]))

    # Split remaining into directors, managers, ICs (~8% dir, 15% mgr, rest IC)
    n_dir = max(10, int(needed * 0.10))
    n_mgr = max(18, int(needed * 0.16))
    levels_queue = [6] * n_dir + [5] * n_mgr + [rng.choice([1, 2, 3, 4]) for _ in range(needed - n_dir - n_mgr)]
    rng.shuffle(levels_queue)

    used_names: set[tuple[str, str]] = {("Ava", "Chen")}
    for n, dept, family, level, first, last in exec_slots:
        used_names.add((first, last))

    next_n = 12
    directors_by_dept: dict[str, list[str]] = defaultdict(list)
    managers_by_dept: dict[str, list[str]] = defaultdict(list)

    for (dept, family), level in zip(remaining_slots, levels_queue):
        while True:
            first = rng.choice(FIRST)
            last = rng.choice(LAST)
            if (first, last) not in used_names:
                used_names.add((first, last))
                break
        if level == 6:
            mgr = exec_by_dept[dept]
        elif level == 5:
            mgr = rng.choice(directors_by_dept[dept]) if directors_by_dept[dept] else exec_by_dept[dept]
        else:
            if managers_by_dept[dept]:
                mgr = rng.choice(managers_by_dept[dept])
            elif directors_by_dept[dept]:
                mgr = rng.choice(directors_by_dept[dept])
            else:
                mgr = exec_by_dept[dept]
        hire = date(rng.randint(2019, 2026), rng.randint(1, 12), rng.randint(1, 28))
        if hire > AS_OF:
            hire = date(2026, 1, rng.randint(5, 20))
        status = "active"
        loc = rng.choice(["loc-sea", "loc-sf", "loc-nyc", "loc-austin", "loc-remote-us", "loc-sea"])
        mode = "remote" if loc == "loc-remote-us" else rng.choice(["hybrid", "hybrid", "onsite"])
        p = add_person(next_n, first, last, dept, family, level, mgr, loc, hire, status, mode)
        if level == 6:
            directors_by_dept[dept].append(p["id"])
        if level == 5:
            managers_by_dept[dept].append(p["id"])
        next_n += 1

    # Terminate ~12 ICs (keep execs/directors active)
    ic_pool = [p for p in people if p["jobLevel"] <= 4 and p["id"] != emp_id(1)]
    for p in rng.sample(ic_pool, 12):
        p["employmentStatus"] = "terminated"
        term = date.fromisoformat(p["hireDate"]) + timedelta(days=rng.randint(200, 900))
        if term > AS_OF:
            term = AS_OF - timedelta(days=rng.randint(10, 80))
        p["terminationDate"] = iso(term)
        p["tenureYears"] = tenure_years(date.fromisoformat(p["hireDate"]), term)

    # 3 pre-hires
    for p in [x for x in people if x["employmentStatus"] == "active" and x["jobLevel"] <= 3][:3]:
        p["employmentStatus"] = "pre_hire"
        p["hireDate"] = "2026-09-01"
        p["tenureYears"] = 0.0

    by_id = {p["id"]: p for p in people}
    reports: dict[str, list[str]] = defaultdict(list)
    for p in people:
        if p["managerId"]:
            reports[p["managerId"]].append(p["id"])
            mgr = by_id.get(p["managerId"])
            if mgr:
                p["managerName"] = mgr["name"]
    for p in people:
        kids = reports.get(p["id"], [])
        p["directReportCount"] = len(kids)
        p["isPeopleManager"] = bool(kids)

    # Departments (after employee ids exist)
    data["departments"].append(_stamp("departments", {
        "id": "dept-company", "departmentId": "dept-company", "name": "ClosedAI",
        "levelType": "company", "parentDepartmentId": None,
        "leaderEmployeeId": emp_id(1), "leaderName": by_id[emp_id(1)]["name"],
        "costCenter": "CC-1000", "layerLevel": 1,
        "headcount": len(people), "openHeadcount": 15,
    }))
    for did, dname, _fam, _t in DEPT_META:
        leader = exec_by_dept[did]
        hc = sum(1 for p in people if p["departmentId"] == did)
        data["departments"].append(_stamp("departments", {
            "id": did, "departmentId": did, "name": dname, "levelType": "department",
            "parentDepartmentId": "dept-company", "leaderEmployeeId": leader,
            "leaderName": by_id[leader]["name"], "costCenter": f"CC-{1000 + abs(hash(did)) % 8000}",
            "layerLevel": 2, "headcount": hc, "openHeadcount": 1,
        }))

    for p in people:
        data["employees"].append(_stamp("employees", p, created=p["hireDate"] + "T09:00:00Z"))

    active = [p for p in people if p["employmentStatus"] == "active"]
    terminated = [p for p in people if p["employmentStatus"] == "terminated"]
    prehire = [p for p in people if p["employmentStatus"] == "pre_hire"]

    # Positions
    for p in people:
        data["positions"].append(_stamp("positions", {
            "id": p["positionId"], "positionId": p["positionId"], "jobId": p["jobId"],
            "title": p["jobTitle"], "departmentId": p["departmentId"],
            "status": "filled" if p["employmentStatus"] != "terminated" else "open",
            "incumbentEmployeeId": p["id"] if p["employmentStatus"] != "terminated" else None,
            "requisitionId": None, "budgetedFte": 1.0, "workLocationId": p["workLocationId"],
        }))
    open_positions = []
    for i in range(1, 16):
        dept, _n, family, _t = rng.choice(DEPT_META)
        level = rng.choice([2, 3, 4])
        pid = f"pos-open-{i:02d}"
        rid = f"req-{i:04d}"
        jid = job_by_family_level[(family, level)]
        open_positions.append((pid, rid, dept, family, level, jid))
        data["positions"].append(_stamp("positions", {
            "id": pid, "positionId": pid, "jobId": jid,
            "title": LEVEL_TITLES[family][level], "departmentId": dept, "status": "open",
            "incumbentEmployeeId": None, "requisitionId": rid, "budgetedFte": 1.0,
            "workLocationId": "loc-sea",
        }))

    # Policies
    policy_rows = [
        ("policy-pto", "Paid Time Off (PTO) Policy", "leave",
         "Full-time employees accrue PTO by tenure: 15 days (<2 yrs), 18 (2-5 yrs), 22 (5+)."),
        ("policy-sick", "Sick Leave Policy", "leave",
         "Full-time employees receive 10 paid sick days per calendar year."),
        ("policy-conduct", "Code of Conduct", "conduct",
         "Employees must act with integrity, respect, and in compliance with law."),
        ("policy-comp", "Compensation Philosophy", "compensation",
         "Pay is set within published bands; annual merit cycle in Q1."),
        ("policy-remote", "Remote Work Policy", "remote_work",
         "Hybrid default; fully remote roles require manager + People approval."),
        ("policy-privacy", "Employee Data Privacy", "data_privacy",
         "HR data is confidential; access is logged and purpose-limited."),
        ("policy-ai", "AI Governance in HR", "ai_governance",
         "High-risk HR AI systems require human review and annual bias audit."),
        ("policy-safety", "Workplace Safety", "safety",
         "Report hazards immediately; OSHA log maintained by Ops."),
        ("policy-security", "Information Security", "security",
         "Annual security awareness training is mandatory."),
        ("policy-immigration", "Immigration & Sponsorship", "immigration",
         "ClosedAI sponsors H-1B and TN where the role qualifies."),
        ("policy-benefits", "Benefits Overview", "benefits",
         "Medical, dental, vision, 401(k) with 4% match, HSA, EAP."),
        ("policy-general", "Employee Handbook", "general",
         "This handbook summarizes employment terms for US employees."),
    ]
    for pid, title, cat, content in policy_rows:
        data["policies"].append(_stamp("policies", {
            "id": pid, "policyId": pid, "title": title, "category": cat, "version": "2026.1",
            "effectiveDate": "2026-01-01", "jurisdiction": "US",
            "acknowledgmentRequired": cat in ("conduct", "security", "ai_governance"),
            "summary": content, "content": content,
            "sourceDocument": "HR-Handbook-2026.pdf", "embeddingId": f"emb-{pid}",
            "ownerId": emp_id(9),
        }))

    people_hr = [p for p in active if p["departmentId"] == "dept-people"]
    recruiter = people_hr[1]["id"] if len(people_hr) > 1 else emp_id(9)

    for pid, rid, dept, family, level, jid in open_positions:
        hm = exec_by_dept[dept]
        band = f"band-{family}-{level}"
        mid = BAND_MID[level]
        data["job_requisitions"].append(_stamp("job_requisitions", {
            "id": rid, "requisitionId": rid, "title": LEVEL_TITLES[family][level],
            "jobId": jid, "departmentId": dept, "positionId": pid,
            "hiringManagerId": hm, "recruiterId": recruiter, "workLocationId": "loc-sea",
            "employmentType": "full_time", "headcount": 1, "filledCount": 0, "status": "open",
            "bandId": band, "salaryRangeMin": int(mid * 0.82), "salaryRangeMax": int(mid * 1.18),
            "openDate": "2026-07-01", "targetFillDate": "2026-09-15", "daysOpen": 49,
        }))

    # Candidates + applications
    n_cand = 90
    for i in range(1, n_cand + 1):
        cid = f"cand-{i:04d}"
        first, last = rng.choice(FIRST), rng.choice(LAST)
        data["candidates"].append(_stamp("candidates", {
            "id": cid, "candidateId": cid, "firstName": first, "lastName": last,
            "name": f"{first} {last}", "email": f"{first.lower()}.{last.lower()}{i}@example.com",
            "phone": f"+1-415-555-{2000 + i:04d}",
            "resumeUrl": f"blob://resumes/{cid}.pdf",
            "source": rng.choice(["inbound", "referral", "sourced", "agency"]),
            "sourceChannel": "LinkedIn",
            "referrerEmployeeId": rng.choice(active)["id"] if rng.random() < 0.25 else None,
            "talentPoolTags": rng.sample(["backend", "python", "product", "sales", "design"], 2),
            "currentTitle": "Engineer", "currentCompany": rng.choice(["Acme", "Globex", "Initech"]),
            "location": "United States", "consentStatus": "granted",
        }))

    stages = ["applied", "screening", "phone_screen", "onsite", "offer", "rejected", "hired"]
    app_n = 0
    hired_apps = []
    for i in range(1, 131):
        app_n += 1
        aid = f"app-{app_n:04d}"
        cand = f"cand-{((i - 1) % n_cand) + 1:04d}"
        rid = f"req-{((i - 1) % 15) + 1:04d}"
        stage = stages[i % len(stages)]
        status = "hired" if stage == "hired" else ("rejected" if stage == "rejected" else "active")
        hired_emp = None
        if stage == "hired" and prehire:
            hired_emp = prehire[len(hired_apps) % len(prehire)]["id"]
            hired_apps.append((aid, rid, cand, hired_emp))
        data["applications"].append(_stamp("applications", {
            "id": aid, "applicationId": aid, "candidateId": cand, "requisitionId": rid,
            "stage": stage, "status": status, "appliedDate": "2026-07-06",
            "dispositionReason": "skills_mismatch" if status == "rejected" else None,
            "score": rng.randint(55, 95), "hiredEmployeeId": hired_emp,
        }))

    data["ai_model_registry"].extend([
        _stamp("ai_model_registry", {
            "id": "ai-resume-screener", "modelId": "ai-resume-screener",
            "name": "Resume Screening Ranker", "purpose": "Rank inbound applications.",
            "provider": "internal", "modelType": "ranking", "riskTier": "high",
            "status": "in_production", "ownerId": recruiter, "usesPii": True,
            "trainingDataAssetIds": ["asset-applications", "asset-candidates"],
            "lastBiasAuditDate": "2026-06-01",
            "biasAuditResult": "No adverse impact >4/5ths rule",
            "humanInLoop": True, "impactAssessmentId": "dpia-0002", "deployedDate": "2026-02-01",
        }),
        _stamp("ai_model_registry", {
            "id": "ai-attrition", "modelId": "ai-attrition",
            "name": "Attrition Risk Predictor", "purpose": "Score flight risk.",
            "provider": "internal", "modelType": "regression", "riskTier": "limited",
            "status": "in_production", "ownerId": emp_id(9), "usesPii": True,
            "trainingDataAssetIds": ["asset-employees"],
            "lastBiasAuditDate": "2026-05-01", "biasAuditResult": "Monitor",
            "humanInLoop": True, "impactAssessmentId": "dpia-0003", "deployedDate": "2026-03-01",
        }),
        _stamp("ai_model_registry", {
            "id": "ai-hr-chat", "modelId": "ai-hr-chat",
            "name": "HR Copilot", "purpose": "Answer HR questions with tools.",
            "provider": "azure-openai", "modelType": "llm", "riskTier": "limited",
            "status": "in_production", "ownerId": emp_id(9), "usesPii": True,
            "trainingDataAssetIds": ["asset-policies"],
            "lastBiasAuditDate": "2026-07-01", "biasAuditResult": "n/a",
            "humanInLoop": True, "impactAssessmentId": "dpia-0001", "deployedDate": "2026-01-15",
        }),
    ])

    # Data asset catalog — one per physical container + key logical entities
    physicals = [
        ("employees", "core_hr", "sensitive_pii", True, ["dateOfBirth", "personalEmail", "phone", "compensation"]),
        ("employee_records", "core_hr", "sensitive_pii", True, ["compensation", "lineItems"]),
        ("org", "core_hr", "internal", False, []),
        ("reference", "governance", "internal", False, []),
        ("recruiting", "talent", "pii", True, ["email", "phone"]),
        ("candidates", "talent", "pii", True, ["email", "phone"]),
        ("operations", "payroll", "confidential", True, []),
        ("governance_logs", "governance", "confidential", True, ["subjectEmployeeId"]),
        ("analytics", "core_hr", "internal", False, []),
        ("survey_responses", "core_hr", "confidential", False, []),
    ]
    for name, domain, klass, pii, fields in physicals:
        data["data_asset_catalog"].append(_stamp("data_asset_catalog", {
            "id": f"asset-{name}", "assetId": f"asset-{name}", "assetName": name,
            "dataDomain": domain, "classification": klass, "containsPii": pii,
            "piiFields": fields or None, "ownerId": emp_id(9), "stewardId": recruiter,
            "retentionScheduleId": "ret-employee", "systemOfRecord": "cosmos:closedai-hr",
            "recordCount": 0, "qualityScore": 0.97,
        }))
    for extra in ("applications", "pay_statements", "policies"):
        data["data_asset_catalog"].append(_stamp("data_asset_catalog", {
            "id": f"asset-{extra}", "assetId": f"asset-{extra}", "assetName": extra,
            "dataDomain": "core_hr", "classification": "confidential", "containsPii": extra != "policies",
            "piiFields": None, "ownerId": emp_id(9), "stewardId": recruiter,
            "retentionScheduleId": "ret-employee", "systemOfRecord": "cosmos:closedai-hr",
            "recordCount": 0, "qualityScore": 0.96,
        }))

    # Compensation history + payroll
    data["payroll_runs"].append(_stamp("payroll_runs", {
        "id": "run-2026-08a", "payRunId": "run-2026-08a", "payGroupId": "pg-us-biweekly",
        "periodStart": "2026-07-16", "periodEnd": "2026-07-31", "payDate": "2026-08-05",
        "status": "paid", "employeeCount": 0, "grossTotal": 0, "netTotal": 0, "taxTotal": 0,
        "currency": "USD", "approvedById": emp_id(9),
    }))
    data["payroll_runs"].append(_stamp("payroll_runs", {
        "id": "run-2026-08b", "payRunId": "run-2026-08b", "payGroupId": "pg-us-biweekly",
        "periodStart": "2026-08-01", "periodEnd": "2026-08-15", "payDate": "2026-08-20",
        "status": "paid", "employeeCount": 0, "grossTotal": 0, "netTotal": 0, "taxTotal": 0,
        "currency": "USD", "approvedById": emp_id(9),
    }))

    leave_n = 0
    ticket_n = 0
    ticket_cats = [
        "pto_leave", "benefits", "payroll", "onboarding", "offboarding", "policy",
        "it_access", "compensation", "employee_relations", "data_privacy", "other",
    ]
    ack_policies = [p for p in data["policies"] if p["acknowledgmentRequired"]]
    skill_ids = [s[0] for s in SKILL_CATALOG]
    gross_08b = 0.0
    net_08b = 0.0
    tax_08b = 0.0
    paid_count = 0

    for idx, p in enumerate(people, start=1):
        eid = p["id"]
        salary = p["compensation"]["annualSalary"]
        data["compensation_records"].append(_stamp("compensation_records", {
            "id": f"comp-{idx:04d}", "compRecordId": f"comp-{idx:04d}", "employeeId": eid,
            "effectiveDate": p["hireDate"], "changeReason": "hire", "baseSalary": salary,
            "currency": "USD", "payFrequency": p["compensation"]["payFrequency"],
            "bandId": p["compensation"]["bandId"], "compaRatio": p["compensation"]["compaRatio"],
            "previousSalary": None, "percentChange": None,
        }))
        if p["employmentStatus"] == "active" and rng.random() < 0.4:
            prev = int(salary / 1.05 / 1000) * 1000
            data["compensation_records"].append(_stamp("compensation_records", {
                "id": f"comp-m-{idx:04d}", "compRecordId": f"comp-m-{idx:04d}", "employeeId": eid,
                "effectiveDate": "2026-01-01", "changeReason": "merit", "baseSalary": salary,
                "currency": "USD", "payFrequency": p["compensation"]["payFrequency"],
                "bandId": p["compensation"]["bandId"], "compaRatio": p["compensation"]["compaRatio"],
                "previousSalary": prev, "percentChange": 5.0,
            }))

        if p["employmentStatus"] in ("active", "on_leave", "pre_hire"):
            coverage = rng.choice(["employee_only", "employee_spouse", "employee_children", "family"])
            deps = []
            if coverage != "employee_only":
                deps.append({"name": f"Sam {p['lastName']}", "relationship": "child", "dateOfBirth": "2018-05-02"})
            data["benefits_elections"].append(_stamp("benefits_elections", {
                "id": f"elec-{idx:04d}", "electionId": f"elec-{idx:04d}", "employeeId": eid,
                "employeeName": p["name"],
                "planElections": [{
                    "planId": "plan-med-ppo", "planType": "medical", "coverageLevel": coverage,
                    "monthlyEmployeeCost": 120 if coverage == "employee_only" else 420,
                    "effectiveDate": "2026-01-01",
                }],
                "retirement401kPercent": 6, "employerMatchPercent": 4,
                "dependents": deps or None, "status": "active",
                "effectiveDate": "2026-01-01", "endDate": None,
            }))

        if p["employmentStatus"] == "active":
            period_gross = round(salary / 26, 2)
            tax = round(period_gross * 0.22, 2)
            k401 = round(period_gross * 0.06, 2)
            med = 60.0
            net = round(period_gross - tax - k401 - med, 2)
            for run_id, ytd_mult in (("run-2026-08a", 15), ("run-2026-08b", 16)):
                data["pay_statements"].append(_stamp("pay_statements", {
                    "id": f"pay-{run_id[-1]}-{idx:04d}", "payStatementId": f"pay-{run_id[-1]}-{idx:04d}",
                    "employeeId": eid, "payRunId": run_id,
                    "grossPay": period_gross, "netPay": net, "currency": "USD",
                    "lineItems": [
                        {"type": "earning", "code": "base", "amount": period_gross},
                        {"type": "tax", "code": "federal", "amount": -tax},
                        {"type": "deduction", "code": "401k", "amount": -k401},
                        {"type": "benefit", "code": "medical", "amount": -med},
                    ],
                    "ytdGross": round(period_gross * ytd_mult, 2),
                    "ytdTax": round(tax * ytd_mult, 2),
                    "ytdNet": round(net * ytd_mult, 2),
                }))
            gross_08b += period_gross
            net_08b += net
            tax_08b += tax
            paid_count += 1

            data["bonus_payouts"].append(_stamp("bonus_payouts", {
                "id": f"bonus-{idx:04d}", "payoutId": f"bonus-{idx:04d}", "employeeId": eid,
                "planName": "FY25 Annual Bonus", "period": "FY2025",
                "targetAmount": int(salary * 0.10), "actualAmount": int(salary * 0.09),
                "targetPercent": 10, "payoutPercent": 90, "status": "paid", "payDate": "2026-03-15",
            }))
            if p["jobLevel"] >= 5:
                data["equity_grants"].append(_stamp("equity_grants", {
                    "id": f"grant-{idx:04d}", "grantId": f"grant-{idx:04d}", "employeeId": eid,
                    "grantType": "rsu", "shares": 2000 * (p["jobLevel"] - 3), "strikePrice": None,
                    "grantDate": p["hireDate"], "vestStartDate": p["hireDate"],
                    "vestingSchedule": "4yr-quarterly-1yr-cliff",
                    "vestedShares": 1000, "status": "active",
                }))

            used = p["ptoSnapshot"]["usedDays"]
            # leave requests that sum close to used days
            remaining_used = used
            while remaining_used > 0:
                leave_n += 1
                chunk = min(remaining_used, rng.randint(1, 3))
                start = date(2026, rng.randint(2, 7), rng.randint(1, 20))
                end = start + timedelta(days=chunk + 1)
                data["leave_requests"].append(_stamp("leave_requests", {
                    "id": f"leave-{leave_n:04d}", "leaveRequestId": f"leave-{leave_n:04d}",
                    "employeeId": eid, "employeeName": p["name"], "leaveType": "pto",
                    "startDate": iso(start), "endDate": iso(end),
                    "businessDays": chunk, "status": "approved",
                    "approverId": p["managerId"] or emp_id(1),
                    "requestedDate": iso(start - timedelta(days=14)), "reason": None,
                }))
                remaining_used -= chunk
            data["leave_balances"].append(_stamp("leave_balances", {
                "id": f"bal-{eid}-pto-2026", "employeeId": eid, "leaveType": "pto", "year": 2026,
                "accruedDays": p["ptoSnapshot"]["accrualDaysPerYear"],
                "usedDays": used, "pendingDays": 0,
                "availableDays": p["ptoSnapshot"]["remainingDays"], "asOf": AS_OF_ISO,
            }))
            data["leave_balances"].append(_stamp("leave_balances", {
                "id": f"bal-{eid}-sick-2026", "employeeId": eid, "leaveType": "sick", "year": 2026,
                "accruedDays": 10, "usedDays": rng.randint(0, 3), "pendingDays": 0,
                "availableDays": 7, "asOf": AS_OF_ISO,
            }))

            if p["flsaStatus"] == "non_exempt":
                data["timesheets"].append(_stamp("timesheets", {
                    "id": f"ts-{idx:04d}", "timesheetId": f"ts-{idx:04d}", "employeeId": eid,
                    "payPeriodStart": "2026-08-01", "payPeriodEnd": "2026-08-15",
                    "entries": [{"date": "2026-08-03", "clockIn": "09:00", "clockOut": "17:30",
                                 "breakMinutes": 30, "hours": 8.0}],
                    "regularHours": 80.0, "overtimeHours": rng.choice([0, 2.5]),
                    "status": "approved", "approverId": p["managerId"],
                }))

            data["performance_reviews"].append(_stamp("performance_reviews", {
                "id": f"rev-{idx:04d}", "reviewId": f"rev-{idx:04d}", "cycleId": "cycle-2026-h1",
                "employeeId": eid, "reviewerId": p["managerId"] or emp_id(1),
                "overallRating": rng.choice([2, 3, 3, 4, 4, 5]), "calibratedRating": None,
                "summary": "Solid contribution this cycle.",
                "strengths": ["ownership", "collaboration"],
                "developmentAreas": ["strategic influence"], "status": "shared",
            }))
            for g in range(1, rng.randint(3, 5)):
                data["goals"].append(_stamp("goals", {
                    "id": f"goal-{idx:04d}-{g}", "goalId": f"goal-{idx:04d}-{g}",
                    "employeeId": eid, "cycleId": "cycle-2026-h1",
                    "title": rng.choice(["Ship billing v2", "Reduce churn", "Hire 2 ICs", "Improve NPS"]),
                    "description": "Cycle goal", "weight": 30, "target": "On track",
                    "progress": rng.randint(40, 95), "status": "active", "parentGoalId": None,
                }))
            for sid in rng.sample(skill_ids, 6):
                data["employee_skills"].append(_stamp("employee_skills", {
                    "id": f"es-{eid}-{sid}", "employeeId": eid, "skillId": sid,
                    "currentLevel": rng.choice(["intermediate", "advanced"]),
                    "targetLevel": "expert", "assessedDate": "2026-06-01",
                    "source": "manager_assessment",
                }))
            for cid, _title, mandatory in courses:
                if mandatory or rng.random() < 0.35:
                    data["course_enrollments"].append(_stamp("course_enrollments", {
                        "id": f"enr-{idx:04d}-{cid[-3:]}", "enrollmentId": f"enr-{idx:04d}-{cid[-3:]}",
                        "employeeId": eid, "courseId": cid, "assignedDate": "2026-01-05",
                        "completedDate": "2026-01-20" if rng.random() < 0.8 else None,
                        "score": 100, "status": "completed" if rng.random() < 0.8 else "in_progress",
                    }))
            if rng.random() < 0.30:
                data["development_plans"].append(_stamp("development_plans", {
                    "id": f"idp-{idx:04d}", "idpId": f"idp-{idx:04d}", "employeeId": eid,
                    "managerId": p["managerId"] or emp_id(1), "period": "2026",
                    "careerGoal": "Next level",
                    "activities": [{"activity": "Lead a cross-team project",
                                    "targetSkillId": "skill-leadership",
                                    "dueDate": "2026-12-31", "status": "in_progress"}],
                    "status": "active",
                }))
            for pol in ack_policies:
                data["policy_acknowledgments"].append(_stamp("policy_acknowledgments", {
                    "id": f"ack-{idx:04d}-{pol['id'][-6:]}", "ackId": f"ack-{idx:04d}-{pol['id'][-6:]}",
                    "employeeId": eid, "policyId": pol["id"],
                    "acknowledgedDate": "2026-01-10", "method": "portal",
                }))
            data["work_authorizations"].append(_stamp("work_authorizations", {
                "id": f"auth-{idx:04d}", "authId": f"auth-{idx:04d}", "employeeId": eid,
                "status": p["workAuthorization"]["status"],
                "documentType": "passport" if p["workAuthorization"]["status"] == "citizen" else "visa",
                "country": p["country"],
                "expirationDate": p["workAuthorization"]["expirationDate"],
                "sponsorship": None if p["workAuthorization"]["status"] != "visa" else {
                    "visaCategory": "H-1B", "sponsorStatus": "approved",
                    "filingDate": "2024-04-01", "approvalDate": "2024-10-01",
                    "renewalDueDate": "2027-06-01",
                },
            }))
            data["assets"].append(_stamp("assets", {
                "id": f"asset-lap-{idx:04d}", "assetId": f"asset-lap-{idx:04d}", "employeeId": eid,
                "assetType": "laptop", "model": "MacBook Pro 14", "serialNumber": f"C02X{idx:04d}",
                "status": "assigned", "assignedDate": p["hireDate"], "returnedDate": None,
            }))
            data["documents"].append(_stamp("documents", {
                "id": f"doc-{idx:04d}", "documentId": f"doc-{idx:04d}", "employeeId": eid,
                "type": "offer_letter", "templateId": "tmpl-offer", "status": "signed",
                "generatedDate": p["hireDate"], "signedDate": p["hireDate"], "verified": True,
                "blobUrl": f"blob://generated-reports/doc-{idx:04d}-offer-letter.pdf",
            }))
            for purpose in ("payroll", "benefits", "performance_analytics"):
                data["consent_records"].append(_stamp("consent_records", {
                    "id": f"consent-{idx:04d}-{purpose[:4]}", "consentId": f"consent-{idx:04d}-{purpose[:4]}",
                    "employeeId": eid, "candidateId": None, "purpose": purpose,
                    "status": "granted", "grantedDate": p["hireDate"],
                    "withdrawnDate": None, "expiryDate": None,
                    "legalBasis": "contract" if purpose == "payroll" else "legitimate_interest",
                }))

    for run in data["payroll_runs"]:
        if run["payRunId"] == "run-2026-08b":
            run["employeeCount"] = paid_count
            run["grossTotal"] = round(gross_08b, 2)
            run["netTotal"] = round(net_08b, 2)
            run["taxTotal"] = round(tax_08b, 2)
        else:
            run["employeeCount"] = paid_count
            run["grossTotal"] = round(gross_08b, 2)
            run["netTotal"] = round(net_08b, 2)
            run["taxTotal"] = round(tax_08b, 2)

    # Tickets across all categories
    for i, cat in enumerate(ticket_cats * 8):
        if i >= 80:
            break
        emp = rng.choice(active)
        ticket_n += 1
        tid = f"tkt-{ticket_n:04d}"
        data["hr_tickets"].append(_stamp("hr_tickets", {
            "id": tid, "ticketId": tid, "employeeId": emp["id"], "employeeName": emp["name"],
            "category": cat, "priority": rng.choice(["low", "medium", "high"]),
            "status": rng.choice(["open", "in_progress", "resolved", "closed"]),
            "subject": f"{cat.replace('_', ' ').title()} question",
            "description": "Employee question for HR.",
            "assigneeId": emp_id(9),
            "policyReferenceId": "policy-pto" if cat == "pto_leave" else None,
            "openedDate": "2026-07-18T10:00:00Z",
            "resolvedDate": "2026-07-18T15:00:00Z",
            "slaDueDate": "2026-07-21T10:00:00Z",
        }))

    for i, cat in enumerate(["pto_leave", "benefits", "payroll", "data_privacy", "onboarding"]):
        data["knowledge_articles"].append(_stamp("knowledge_articles", {
            "id": f"kb-{i + 1:04d}", "articleId": f"kb-{i + 1:04d}",
            "title": f"How {cat.replace('_', ' ')} works", "category": cat,
            "content": "See the related policy for canonical numbers.",
            "relatedPolicyId": "policy-pto" if cat == "pto_leave" else "policy-privacy",
            "views": rng.randint(40, 500), "lastReviewedDate": "2026-06-01",
        }))

    data["integrations"].append(_stamp("integrations", {
        "id": "intg-hris-payroll", "integrationId": "intg-hris-payroll",
        "name": "HRIS to Payroll Sync", "sourceSystem": "cosmos:closedai-hr",
        "targetSystem": "payroll-vendor", "vendorId": "vendor-adp",
        "dataAssetIds": ["asset-employees", "asset-pay_statements"],
        "direction": "outbound", "frequency": "daily", "status": "active",
        "lastSyncAt": "2026-08-18T02:00:00Z", "ownerId": emp_id(9),
    }))
    data["integrations"].append(_stamp("integrations", {
        "id": "intg-ats", "integrationId": "intg-ats", "name": "ATS Sync",
        "sourceSystem": "greenhouse", "targetSystem": "cosmos:closedai-hr",
        "vendorId": "vendor-greenhouse", "dataAssetIds": ["asset-candidates"],
        "direction": "inbound", "frequency": "hourly", "status": "active",
        "lastSyncAt": "2026-08-18T17:00:00Z", "ownerId": recruiter,
    }))

    # Interviews + offers
    intv_n = 0
    for app in data["applications"]:
        if app["stage"] in ("phone_screen", "onsite", "offer", "hired"):
            intv_n += 1
            data["interviews"].append(_stamp("interviews", {
                "id": f"intv-{intv_n:04d}", "interviewId": f"intv-{intv_n:04d}",
                "applicationId": app["applicationId"], "requisitionId": app["requisitionId"],
                "type": "technical" if "eng" in app["requisitionId"] else "behavioral",
                "scheduledAt": "2026-07-25T17:00:00Z", "durationMinutes": 60,
                "interviewerIds": [emp_id(2), emp_id(3)],
                "status": "completed",
                "scorecards": [{"interviewerId": emp_id(2), "competency": "coding", "rating": 4, "notes": "Strong."}],
                "overallRecommendation": "yes",
            }))
        if app["stage"] in ("offer", "hired"):
            data["offers"].append(_stamp("offers", {
                "id": f"offer-{app['applicationId'][-4:]}", "offerId": f"offer-{app['applicationId'][-4:]}",
                "applicationId": app["applicationId"], "requisitionId": app["requisitionId"],
                "candidateId": app["candidateId"], "baseSalary": 165000, "currency": "USD",
                "signOnBonus": 10000, "targetBonusPercent": 10, "equityShares": 1500,
                "startDate": "2026-09-01",
                "status": "accepted" if app["stage"] == "hired" else "extended",
                "extendedDate": "2026-08-05", "expiryDate": "2026-08-15",
                "decisionDate": "2026-08-08" if app["stage"] == "hired" else None,
                "approverIds": [emp_id(2), emp_id(1)],
            }))

    # Feedback / recognition / succession / mobility
    fb_n = 0
    for p in rng.sample(active, min(60, len(active))):
        peers = [x for x in active if x["departmentId"] == p["departmentId"] and x["id"] != p["id"]]
        if not peers:
            continue
        fb_n += 1
        reviewer = rng.choice(peers)
        data["feedback"].append(_stamp("feedback", {
            "id": f"fb-{fb_n:04d}", "feedbackId": f"fb-{fb_n:04d}",
            "revieweeId": p["id"], "employeeId": p["id"], "reviewerId": reviewer["id"],
            "cycleId": "cycle-2026-h1", "relationship": "peer",
            "competencyScores": [{"competency": "collaboration", "score": 4}],
            "comments": "Great partner.", "submittedDate": "2026-06-20",
        }))
    for i, p in enumerate(rng.sample(active, 50), start=1):
        data["recognition_awards"].append(_stamp("recognition_awards", {
            "id": f"award-{i:04d}", "awardId": f"award-{i:04d}", "employeeId": p["id"],
            "grantedById": p["managerId"] or emp_id(1),
            "type": rng.choice(["spot_bonus", "peer_kudos", "value_award"]),
            "points": 100, "amount": rng.choice([0, 250, 500]),
            "reason": "Exceeded expectations.", "grantedDate": "2026-07-30",
        }))

    for n, dept, family, level, _f, _l in exec_slots:
        pos = f"pos-{n:04d}"
        ready = reports.get(emp_id(n), [])[:3]
        data["succession_plans"].append(_stamp("succession_plans", {
            "id": f"succ-{n:04d}", "successionPlanId": f"succ-{n:04d}", "positionId": pos,
            "incumbentEmployeeId": emp_id(n),
            "readyNowIds": ready[:1], "ready1YearIds": ready[1:2], "ready3YearIds": ready[2:3],
            "riskLevel": rng.choice(["low", "medium", "high"]),
        }))

    for i, p in enumerate(rng.sample(active, 10), start=1):
        data["internal_mobility"].append(_stamp("internal_mobility", {
            "id": f"mob-{i:04d}", "mobilityId": f"mob-{i:04d}", "employeeId": p["id"],
            "fromPositionId": p["positionId"], "targetRequisitionId": "req-0001",
            "targetPositionId": "pos-open-01", "type": rng.choice(["promotion", "lateral", "transfer"]),
            "status": rng.choice(["requested", "in_review", "approved"]),
            "requestedDate": "2026-07-10", "effectiveDate": None,
        }))

    for i, (aid, rid, cand, hired_emp) in enumerate(hired_apps, start=1):
        data["background_checks"].append(_stamp("background_checks", {
            "id": f"bgc-{i:04d}", "checkId": f"bgc-{i:04d}", "candidateId": cand,
            "employeeId": hired_emp, "vendorId": "vendor-checkr", "status": "clear",
            "requestedDate": "2026-08-06", "completedDate": "2026-08-10",
            "result": "No adverse findings.",
        }))

    # Survey responses + engagement snapshots
    for i in range(1, 81):
        dept = rng.choice(DEPT_META)[0]
        data["survey_responses"].append(_stamp("survey_responses", {
            "id": f"resp-{i:04d}", "responseId": f"resp-{i:04d}", "surveyId": "survey-2026-q2",
            "employeeId": None, "departmentId": dept,
            "scores": [{"questionId": "q1", "score": rng.randint(3, 5)}],
            "comments": None, "submittedDate": "2026-04-20",
            "engagementIndex": round(rng.uniform(6.5, 8.8), 1),
        }))

    # ER / compliance
    case_cats = ["grievance", "harassment", "discrimination", "misconduct", "performance",
                 "policy_violation", "workplace_conflict", "whistleblower", "accommodation", "other"]
    for i, cat in enumerate(case_cats * 2, start=1):
        emp = rng.choice(active)
        data["er_cases"].append(_stamp("er_cases", {
            "id": f"case-{i:04d}", "caseId": f"case-{i:04d}", "employeeId": emp["id"],
            "reportedById": emp["managerId"], "category": cat,
            "severity": rng.choice(["low", "medium", "high"]),
            "status": rng.choice(["open", "investigating", "resolved", "closed"]),
            "assigneeId": emp_id(9), "confidentialityLevel": "restricted",
            "openedDate": "2026-07-12", "closedDate": None,
            "summary": f"{cat.replace('_', ' ')} matter.",
            "notes": [{"authorId": emp_id(9), "timestamp": "2026-07-13T10:00:00Z",
                       "content": "Intake completed.", "actionType": "intake"}],
            "investigation": None,
        }))
    for i in range(1, 9):
        case = data["er_cases"][i - 1]
        data["disciplinary_actions"].append(_stamp("disciplinary_actions", {
            "id": f"disc-{i:04d}", "actionId": f"disc-{i:04d}",
            "employeeId": case["employeeId"], "caseId": case["caseId"],
            "actionType": rng.choice(["verbal_warning", "written_warning", "final_warning"]),
            "issuedById": emp_id(9), "effectiveDate": "2026-07-20",
            "expirationDate": "2027-07-20", "reason": "Policy concern.",
        }))
    for i in range(1, 11):
        emp = rng.choice(active)
        data["accommodation_requests"].append(_stamp("accommodation_requests", {
            "id": f"acc-{i:04d}", "accommodationId": f"acc-{i:04d}", "employeeId": emp["id"],
            "requestDate": "2026-06-01", "conditionCategory": rng.choice(["mobility", "visual", "cognitive"]),
            "requestedAccommodation": "Ergonomic setup",
            "status": rng.choice(["requested", "approved", "implemented", "interactive_process"]),
            "handlerId": emp_id(9), "approvedAccommodation": "Standing desk",
            "interactiveProcessNotes": "Completed with facilities.", "reviewDate": "2027-06-01",
        }))

    data["compliance_audits"].extend([
        _stamp("compliance_audits", {
            "id": "audit-0001", "auditId": "audit-0001", "type": "i9", "scope": "US hires 2026",
            "requirementId": "req-comp-i9", "startDate": "2026-04-01", "completedDate": "2026-04-20",
            "leadId": emp_id(9),
            "findings": [{"finding": "2 late I-9s", "severity": "medium",
                          "remediation": "Retrain coordinators", "status": "resolved"}],
            "overallStatus": "compliant",
        }),
        _stamp("compliance_audits", {
            "id": "audit-0002", "auditId": "audit-0002", "type": "pay_equity", "scope": "US, all depts",
            "requirementId": None, "startDate": "2026-05-01", "completedDate": "2026-06-01",
            "leadId": emp_id(9),
            "findings": [{"finding": "2% unexplained gap in Eng L4", "severity": "medium",
                          "remediation": "Adjust 3 salaries", "status": "in_progress"}],
            "overallStatus": "remediation",
        }),
        _stamp("compliance_audits", {
            "id": "audit-0003", "auditId": "audit-0003", "type": "data_privacy", "scope": "HR systems",
            "requirementId": "req-comp-gdpr", "startDate": "2026-07-01", "completedDate": None,
            "leadId": emp_id(9), "findings": [], "overallStatus": "at_risk",
        }),
    ])

    dsar_types = ["access", "rectification", "erasure", "portability", "restriction", "objection"]
    for i, t in enumerate(dsar_types + ["access", "erasure"], start=1):
        emp = rng.choice(people)
        data["dsar_requests"].append(_stamp("dsar_requests", {
            "id": f"dsar-{i:04d}", "dsarId": f"dsar-{i:04d}",
            "requesterEmployeeId": emp["id"], "requesterCandidateId": None,
            "type": t, "status": rng.choice(["received", "in_progress", "completed", "extended"]),
            "receivedDate": "2026-08-01", "dueDate": "2026-08-31",
            "completedDate": "2026-08-15" if t == "access" else None,
            "assigneeId": emp_id(9),
            "assetsInScope": ["asset-employees", "asset-pay_statements"],
            "resolutionNotes": None,
        }))

    for i in range(1, 201):
        emp = rng.choice(active)
        subj = rng.choice(active)
        data["data_access_logs"].append(_stamp("data_access_logs", {
            "id": f"acl-{i:06d}", "logId": f"acl-{i:06d}",
            "accessorId": emp_id(9) if rng.random() < 0.5 else emp["id"],
            "assetId": rng.choice(["asset-employees", "asset-employee_records", "asset-pay_statements"]),
            "subjectEmployeeId": subj["id"],
            "action": rng.choice(["read", "export", "update"]),
            "purpose": rng.choice(["payroll_processing", "hr_ticket", "audit", "ai_processing"]),
            "classification": "sensitive_pii",
            "timestamp": f"2026-08-{(i % 18) + 1:02d}T12:00:00Z",
            "approved": True, "sourceSystem": "hr-agent",
        }))
    for i in range(1, 151):
        cand = f"cand-{(i % 90) + 1:04d}"
        data["ai_usage_logs"].append(_stamp("ai_usage_logs", {
            "id": f"aiu-{i:06d}", "usageId": f"aiu-{i:06d}",
            "modelId": rng.choice(["ai-resume-screener", "ai-attrition", "ai-hr-chat"]),
            "userId": recruiter if rng.random() < 0.6 else emp_id(9),
            "subjectEmployeeId": rng.choice(active)["id"] if rng.random() < 0.4 else None,
            "subjectCandidateId": cand if rng.random() < 0.6 else None,
            "decision": rng.choice(["advance", "hold", "reject", None]),
            "confidence": round(rng.uniform(0.55, 0.95), 2),
            "humanOverride": rng.random() < 0.12,
            "overrideReason": "Recruiter judgment" if rng.random() < 0.12 else None,
            "timestamp": f"2026-07-{(i % 28) + 1:02d}T09:00:00Z",
        }))
    dq_rules = ["completeness", "validity", "uniqueness", "consistency", "referential_integrity", "timeliness"]
    for i in range(1, 31):
        data["data_quality_issues"].append(_stamp("data_quality_issues", {
            "id": f"dqi-{i:04d}", "issueId": f"dqi-{i:04d}",
            "assetId": rng.choice(["asset-employees", "asset-employee_records", "asset-candidates"]),
            "ruleType": rng.choice(dq_rules), "field": rng.choice(["personalEmail", "managerId", "phone"]),
            "affectedRecordCount": rng.randint(1, 18),
            "severity": rng.choice(["info", "low", "medium", "high"]),
            "status": rng.choice(["open", "in_progress", "resolved"]),
            "detectedDate": "2026-08-15", "resolvedDate": None,
            "ownerId": emp_id(9), "description": "Data quality finding from automated scan.",
        }))

    # Lifecycle
    recent_hires = sorted(active, key=lambda x: x["hireDate"], reverse=True)[:15]
    for i, p in enumerate(recent_hires, start=1):
        data["onboarding_checklists"].append(_stamp("onboarding_checklists", {
            "id": f"onb-{i:04d}", "checklistId": f"onb-{i:04d}", "employeeId": p["id"],
            "employeeName": p["name"], "jobId": p["jobId"], "departmentId": p["departmentId"],
            "startDate": p["hireDate"], "status": "in_progress" if i < 6 else "completed",
            "hrOwnerId": emp_id(9), "managerId": p["managerId"] or emp_id(1),
            "tasks": [
                {"key": "i9", "label": "I-9 Verification", "status": "completed",
                 "dueDate": p["hireDate"], "completedDate": p["hireDate"]},
                {"key": "laptop", "label": "Laptop assigned", "status": "completed",
                 "dueDate": p["hireDate"], "completedDate": p["hireDate"]},
            ],
            "percentComplete": 0.5 if i < 6 else 1.0,
        }))
    for i, p in enumerate(terminated[:6], start=1):
        data["offboarding_checklists"].append(_stamp("offboarding_checklists", {
            "id": f"off-{i:04d}", "checklistId": f"off-{i:04d}", "employeeId": p["id"],
            "employeeName": p["name"], "separationType": rng.choice(["voluntary", "involuntary"]),
            "reason": "Career growth", "lastDay": p["terminationDate"],
            "status": "completed", "hrOwnerId": emp_id(9),
            "tasks": [{"key": "access_revoke", "label": "Revoke system access", "status": "completed",
                       "dueDate": p["terminationDate"], "completedDate": p["terminationDate"]}],
            "rehireEligible": True,
        }))
        data["exit_interviews"].append(_stamp("exit_interviews", {
            "id": f"exit-{i:04d}", "exitInterviewId": f"exit-{i:04d}", "employeeId": p["id"],
            "conductedDate": p["terminationDate"], "conductedById": emp_id(9),
            "responses": [{"question": "Primary reason for leaving?", "answer": "Career growth",
                           "sentiment": "neutral"}],
            "primaryReason": "career_growth", "themes": ["growth", "compensation"],
            "wouldRecommend": True, "rehireEligible": True,
        }))

    low_rated = [r for r in data["performance_reviews"] if r["overallRating"] <= 2][:5]
    for i, rev in enumerate(low_rated, start=1):
        data["pips"].append(_stamp("pips", {
            "id": f"pip-{i:04d}", "pipId": f"pip-{i:04d}", "employeeId": rev["employeeId"],
            "ownerId": rev["reviewerId"], "startDate": "2026-07-01", "endDate": "2026-09-30",
            "issues": ["missed deadlines"],
            "goals": [{"goal": "Deliver sprint commitments", "dueDate": "2026-08-15", "status": "in_progress"}],
            "checkInDates": ["2026-07-15", "2026-08-15"], "outcome": "in_progress",
            "linkedCaseId": data["er_cases"][0]["caseId"] if i == 1 else None,
        }))

    # Workforce plans + snapshots
    months = [f"2025-{m:02d}" for m in range(9, 13)] + [f"2026-{m:02d}" for m in range(1, 9)]
    for did, dname, _f, _t in [("dept-company", "ClosedAI", "", 0)] + DEPT_META:
        hc = sum(1 for p in people if did == "dept-company" or p["departmentId"] == did)
        data["workforce_plans"].append(_stamp("workforce_plans", {
            "id": f"wfp-{did}-2026", "planId": f"wfp-{did}-2026", "departmentId": did,
            "fiscalYear": "FY2026", "period": "FY2026", "scenarioName": "base",
            "currentHeadcount": hc, "plannedHeadcount": hc + 4,
            "demandFte": hc + 4, "supplyFte": hc, "gapFte": 4, "plannedHires": 6,
            "projectedAttrition": 2, "plannedCompCost": hc * 150000,
            "assumptions": "12% attrition",
            "forecasts": [{"period": "2026-Q4", "projectedHeadcount": hc + 2,
                           "projectedHires": 3, "projectedAttrition": 1}],
        }))
        eng = round(rng.uniform(6.8, 8.4), 1)
        data["engagement_snapshots"].append(_stamp("engagement_snapshots", {
            "id": f"eng-2026-q2-{did}", "snapshotId": f"eng-2026-q2-{did}",
            "departmentId": did, "period": "2026-Q2", "surveyId": "survey-2026-q2",
            "engagementIndex": eng, "participationRate": 0.82, "enpsScore": 28,
            "representation": {"female": 0.42, "male": 0.54},
        }))
        for period in months:
            data["org_snapshots"].append(_stamp("org_snapshots", {
                "id": f"snap-{period}-{did}", "snapshotId": f"snap-{period}-{did}",
                "period": period, "scope": "company" if did == "dept-company" else "department",
                "departmentId": None if did == "dept-company" else did,
                "headcount": hc, "hires": rng.randint(0, 4), "terminations": rng.randint(0, 2),
                "attritionRate": round(rng.uniform(0.005, 0.03), 3),
                "avgSpanOfControl": 5.5, "layers": 5, "avgTenureYears": 3.2,
                "femalePercent": 0.42, "avgCompaRatio": 0.97, "openReqs": 15 if did == "dept-company" else 1,
            }))

    # Fill recordCount on catalog from generated volumes (physical names)
    counts = {k: len(v) for k, v in data.items()}
    mapping = entity_to_container()
    physical_counts: dict[str, int] = defaultdict(int)
    for entity, n in counts.items():
        physical_counts[mapping[entity]] += n
    for asset in data["data_asset_catalog"]:
        name = asset["assetName"]
        asset["recordCount"] = physical_counts.get(name, counts.get(name, 0))

    return dict(data)


def _cosmos_client():
    from azure.cosmos import CosmosClient

    load_env()
    uri = (os.getenv("COSMOS_URI") or os.getenv("COSMOS_ENDPOINT") or "").strip().strip('"')
    key = (os.getenv("COSMOS_KEY") or "").strip().strip('"')
    if not uri or not key:
        raise SystemExit("Set COSMOS_URI and COSMOS_KEY in .env")
    return CosmosClient(
        uri,
        credential=key,
        retry_total=20,
        retry_throttle_total=40,
        retry_throttle_backoff_max=60,
    )


def write_all(data: dict[str, list[dict[str, Any]]], writer: AdaptiveWriter) -> None:
    order = population_order()
    total = sum(len(data.get(e, [])) for e in order)
    done = 0
    started = time.monotonic()
    print(f"Writing {total} documents across {len(order)} entity types "
          f"(adaptive cap starting at {writer.target_ru_s:.0f} RU/s)...")
    for entity in order:
        docs = data.get(entity, [])
        if not docs:
            print(f"  ! {entity}: 0 docs (unexpected)")
            continue
        for doc in docs:
            writer.upsert(entity, doc)
            done += 1
            if done % 100 == 0:
                elapsed = time.monotonic() - started
                rate = done / elapsed if elapsed else 0
                print(f"  ... {done}/{total} ({rate:.1f} docs/s, target {writer.target_ru_s:.0f} RU/s, "
                      f"throttles={writer.throttle_count})")
        print(f"  + {entity}: {len(docs)}")
    elapsed = time.monotonic() - started
    print(f"Done. {writer.written} upserts in {elapsed/60:.1f} min "
          f"({writer.throttle_count} throttles handled).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    print(f"Generating seed world (seed={args.seed}, employees={N_EMPLOYEES})...")
    data = generate(rng)
    mapping = entity_to_container()
    print("Document counts by entity:")
    total = 0
    for entity in population_order():
        n = len(data.get(entity, []))
        total += n
        print(f"  {entity:28s} {n:5d}  -> {mapping[entity]}")
    missing = [e for e in population_order() if not data.get(e)]
    if missing:
        raise SystemExit(f"Missing entities: {missing}")
    print(f"Total documents: {total}")
    if args.dry_run:
        print("Dry run — no writes.")
        return

    client = _cosmos_client()
    db = client.get_database_client(DATABASE_NAME)
    writer = AdaptiveWriter(db)
    write_all(data, writer)


if __name__ == "__main__":
    main()
