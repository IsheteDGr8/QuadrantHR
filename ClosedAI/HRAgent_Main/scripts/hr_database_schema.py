"""
ClosedAI HR — Greenfield Database Schema & Provisioning
=======================================================

A brand-new, EXTREMELY detailed and interconnected Cosmos DB, purpose-built so
that (almost) every one of the 146 HR skills has real, connected data to operate
on — including the ones that today have nothing to work with (data governance,
payroll, benefits, performance, workforce planning, compliance, etc.).

This is an IMPLEMENTATION FILE, not prose:

  * ``DATABASE_NAME``   — the new database (leaves the old ``closedai-db`` untouched)
  * ``ENUMS``           — the only allowed values for every enumerated field
  * ``CONTAINERS``      — the full, machine-readable schema for every container
                          (partition key, unique keys, indexing, every field with
                          type/enum/foreign-key/derived flags, and an example doc)
  * ``foreign_keys()``  — auto-derived FK graph (from each field's ``ref``) so the
                          populator and the validator share ONE source of truth
  * ``provision()``     — creates the database + all containers, idempotently
  * CLI                 — ``python hr_database_schema.py provision | print-spec |
                          fk-graph | markdown``

How Claude (or anyone) populates it
-----------------------------------
1. Run ``provision`` to create the empty database + containers.
2. Import ``CONTAINERS`` / ``ENUMS`` / ``foreign_keys`` from this module and
   generate documents that CONFORM to each ``ContainerSpec.fields`` — using the
   typed IDs, camelCase names, enum values, and FK targets defined here.
3. Fill data in dependency order (``population_order()``): foundation/org spine
   first, then everything that references it. Derived fields (``derived=True``)
   must be COMPUTED from their source of truth, never hand-set.
4. Validate with the rules in ``REFERENTIAL_RULES`` + ``foreign_keys()`` +
   ``COVERAGE_TARGETS`` before declaring the build done.

Global conventions (enforced everywhere)
----------------------------------------
* Every doc has ``id`` == its typed business key (e.g. ``id == employeeId ==
  "emp-0001"``). IDs are ``<prefix>-<zero-padded-int>`` — never a raw name/UUID.
* All field names are camelCase. No snake_case.
* Foreign keys are ALWAYS IDs (suffix ``Id`` / ``Ids``) that resolve to a real
  document. A denormalized ``*Name`` cache may accompany a FK for display; the
  ``Id`` is the source of truth and the ``Name`` is regenerated to match.
* Standard metadata on every doc: ``company``, ``schemaVersion``, ``createdAt``,
  ``updatedAt`` (ISO 8601 UTC).
* Money = major units (165000 = $165,000) + ``currency``. Dates = "YYYY-MM-DD".
  Timestamps = ISO 8601 "...Z". Unknown = ``null`` (never "" / "N/A").

Connection: reads ``COSMOS_URI`` / ``COSMOS_KEY`` from the environment (.env).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field as dc_field
from typing import Any


# ---------------------------------------------------------------------------
# Target database
# ---------------------------------------------------------------------------
# A NEW database. The legacy, inconsistent `closedai-db` is left in place so we
# can cut over cleanly and roll back if needed.
DATABASE_NAME = os.getenv("COSMOS_NEW_DATABASE", "closedai-hr")

# Constant tenant value stamped on every document in this single-company dataset.
COMPANY = "ClosedAI"
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Enumerations — the ONLY allowed values for each enumerated field
# ---------------------------------------------------------------------------
ENUMS: dict[str, list[str]] = {
    "employmentStatus": ["active", "on_leave", "terminated", "pre_hire"],
    "employmentType": ["full_time", "part_time", "contract", "intern", "temp"],
    "flsaStatus": ["exempt", "non_exempt"],
    "workMode": ["onsite", "hybrid", "remote"],
    "payFrequency": ["weekly", "biweekly", "semimonthly", "monthly", "annual"],
    "workAuthStatus": ["citizen", "permanent_resident", "visa", "pending"],
    # jobLevel is an int 1..8 (1-4 IC, 5 manager, 6 director/head, 7 VP/CxO, 8 CEO)
    "leaveType": ["pto", "sick", "parental", "fmla", "bereavement", "jury_duty", "unpaid", "sabbatical"],
    "leaveStatus": ["pending", "approved", "rejected", "cancelled", "taken"],
    "planType": ["medical", "dental", "vision", "retirement_401k", "hsa", "fsa", "life", "disability", "eap"],
    "coverageLevel": ["employee_only", "employee_spouse", "employee_children", "family", "waived"],
    "payrollStatus": ["draft", "processing", "processed", "paid", "cancelled"],
    "payLineType": ["earning", "deduction", "tax", "benefit", "reimbursement", "garnishment"],
    "requisitionStatus": ["draft", "open", "on_hold", "filled", "cancelled"],
    "applicationStage": ["applied", "screening", "phone_screen", "onsite", "offer", "hired", "rejected", "withdrawn"],
    "offerStatus": ["draft", "pending_approval", "extended", "accepted", "declined", "rescinded", "expired"],
    "interviewType": ["phone_screen", "technical", "behavioral", "panel", "onsite", "hiring_manager", "final"],
    "recommendation": ["strong_yes", "yes", "no", "strong_no", "no_decision"],
    "separationType": ["voluntary", "involuntary", "retirement", "end_of_contract"],
    "checklistStatus": ["not_started", "in_progress", "completed", "overdue"],
    "taskStatus": ["pending", "in_progress", "completed", "blocked", "na"],
    "reviewCycleType": ["annual", "mid_year", "quarterly", "probationary", "project"],
    "reviewStatus": ["not_started", "self_review", "manager_review", "calibration", "shared", "acknowledged"],
    # overallRating is an int 1..5 (1 below, 3 meets, 5 exceeds)
    "goalStatus": ["draft", "active", "at_risk", "achieved", "missed", "cancelled"],
    "feedbackRelationship": ["self", "manager", "peer", "direct_report", "skip_level", "external"],
    "pipOutcome": ["in_progress", "successful", "extended", "termination", "cancelled"],
    "courseModality": ["elearning", "instructor_led", "virtual", "blended", "on_the_job"],
    "enrollmentStatus": ["assigned", "in_progress", "completed", "expired", "waived"],
    "skillSource": ["self_assessment", "manager_assessment", "certification", "assessment_test", "inferred"],
    "ticketCategory": ["pto_leave", "benefits", "payroll", "onboarding", "offboarding", "policy",
                        "it_access", "compensation", "employee_relations", "data_privacy", "other"],
    "ticketPriority": ["low", "medium", "high", "urgent"],
    "ticketStatus": ["open", "in_progress", "waiting", "resolved", "closed"],
    "caseCategory": ["grievance", "harassment", "discrimination", "misconduct", "performance",
                     "policy_violation", "workplace_conflict", "whistleblower", "accommodation", "other"],
    "caseStatus": ["open", "investigating", "pending_decision", "resolved", "closed", "escalated"],
    "caseSeverity": ["low", "medium", "high", "critical"],
    "disciplinaryType": ["verbal_warning", "written_warning", "final_warning", "suspension", "termination"],
    "accommodationStatus": ["requested", "interactive_process", "approved", "denied", "implemented", "under_review"],
    "policyCategory": ["leave", "benefits", "conduct", "compensation", "safety", "security",
                       "remote_work", "immigration", "data_privacy", "ai_governance", "general"],
    "documentType": ["offer_letter", "i9", "nda", "w4", "handbook_ack", "emergency_contact",
                     "performance_review", "disciplinary", "separation_agreement", "visa_filing", "other"],
    "assetType": ["laptop", "monitor", "phone", "badge", "peripheral", "software_license", "vehicle", "other"],
    "assetStatus": ["in_stock", "assigned", "returned", "retired", "lost"],
    "surveyType": ["engagement", "pulse", "onboarding", "exit", "dei", "manager_effectiveness", "wellbeing"],
    "complianceStatus": ["compliant", "at_risk", "non_compliant", "remediation", "not_applicable"],
    "backgroundCheckStatus": ["not_started", "in_progress", "clear", "flagged", "failed"],
    "vendorCategory": ["ats", "hris", "payroll", "lms", "benefits_broker", "background_check",
                       "immigration", "assessment", "engagement", "consulting", "other"],
    # ---- Data governance / AI ----
    "dataClassification": ["public", "internal", "confidential", "restricted", "pii", "sensitive_pii"],
    "aiRiskTier": ["minimal", "limited", "high", "unacceptable"],
    "aiSystemStatus": ["proposed", "in_review", "approved", "in_production", "retired", "blocked"],
    "consentStatus": ["granted", "withdrawn", "expired", "not_requested"],
    "consentPurpose": ["payroll", "benefits", "performance_analytics", "ai_processing",
                       "background_check", "marketing", "third_party_sharing"],
    "dsarType": ["access", "rectification", "erasure", "portability", "restriction", "objection"],
    "dsarStatus": ["received", "verifying", "in_progress", "completed", "rejected", "extended"],
    "dqSeverity": ["info", "low", "medium", "high", "critical"],
    "dqStatus": ["open", "acknowledged", "in_progress", "resolved", "wont_fix"],
    "integrationStatus": ["active", "degraded", "failed", "disabled"],
    "orgLevelType": ["company", "division", "department", "team"],
}


# ---------------------------------------------------------------------------
# Field + ContainerSpec model
# ---------------------------------------------------------------------------
def F(
    type_: str,
    *,
    required: bool = True,
    enum: str | None = None,
    ref: str | None = None,
    derived: bool = False,
    desc: str = "",
) -> dict[str, Any]:
    """Compact field descriptor.

    type_   : "string" | "int" | "number" | "bool" | "date" | "datetime"
              | "object" | "array<...>" | "money"
    enum    : key into ENUMS whose list is the allowed value set
    ref     : "<container>.<field>" foreign key that MUST resolve to a real doc
    derived : value is COMPUTED from a source of truth (never hand-authored)
    """
    if enum and enum not in ENUMS:
        raise ValueError(f"Unknown enum '{enum}'")
    return {
        "type": type_,
        "required": required,
        "enum": enum,
        "ref": ref,
        "derived": derived,
        "desc": desc,
    }


@dataclass
class ContainerSpec:
    name: str
    partition_key: str          # e.g. "/employeeId"
    domain: str
    description: str
    fields: dict[str, dict]
    example: dict
    seed: str = ""              # target volume / coverage guidance for the populator
    unique_keys: list[list[str]] = dc_field(default_factory=list)
    exclude_paths: list[str] = dc_field(default_factory=list)  # big text -> not indexed
    composite_indexes: list[list[dict]] = dc_field(default_factory=list)

    def foreign_keys(self) -> list[tuple[str, str]]:
        """[(localField, 'targetContainer.targetField'), ...]"""
        out = []
        for fname, spec in self.fields.items():
            if spec.get("ref"):
                out.append((fname, spec["ref"]))
        return out


# Standard metadata every container gets appended automatically.
_META_FIELDS = {
    "recordType": F("string", desc="Entity type discriminator (== the entity name, e.g. 'employee', "
                                   "'pay_statement'). Used to filter within a physical container."),
    "company": F("string", desc="Constant 'ClosedAI'."),
    "schemaVersion": F("int", desc="Schema version stamp."),
    "createdAt": F("datetime", desc="Record creation, ISO 8601 UTC."),
    "updatedAt": F("datetime", desc="Last update, ISO 8601 UTC."),
}


def _spec(**kwargs) -> ContainerSpec:
    """Build a ContainerSpec, auto-adding standard metadata fields."""
    kwargs["fields"] = {**kwargs["fields"], **_META_FIELDS}
    return ContainerSpec(**kwargs)


# Registry populated by the domain sections below (imported as a package).
CONTAINERS: list[ContainerSpec] = []


def register(spec: ContainerSpec) -> ContainerSpec:
    CONTAINERS.append(spec)
    return spec


# ===========================================================================
# DOMAIN 1 — FOUNDATION / ORG SPINE  (build first; everything references these)
# ===========================================================================

register(_spec(
    name="employees",
    partition_key="/employeeId",
    domain="foundation",
    description="System-of-record for a person's current state. One coherent org.",
    unique_keys=[["/employeeId"], ["/workEmail"]],
    composite_indexes=[[{"path": "/departmentId", "order": "ascending"},
                        {"path": "/employmentStatus", "order": "ascending"}]],
    seed="~250 people, ONE valid manager tree (1 CEO root, <=5 layers), salaries within bands.",
    fields={
        "id": F("string", desc="== employeeId, e.g. 'emp-0006'."),
        "employeeId": F("string", desc="Typed id 'emp-####'."),
        "firstName": F("string"),
        "lastName": F("string"),
        "name": F("string", derived=True, desc="firstName + ' ' + lastName."),
        "preferredName": F("string", required=False),
        "workEmail": F("string", desc="Unique. '<first>.<last>@closedai.com'."),
        "personalEmail": F("string", required=False),
        "phone": F("string", required=False),
        "dateOfBirth": F("date", required=False),
        "gender": F("string", required=False, desc="Optional self-ID; for DEI analytics."),
        "ethnicity": F("string", required=False, desc="Optional self-ID; for DEI analytics."),
        "employmentStatus": F("string", enum="employmentStatus"),
        "employmentType": F("string", enum="employmentType"),
        "flsaStatus": F("string", enum="flsaStatus"),
        "hireDate": F("date"),
        "terminationDate": F("date", required=False),
        "tenureYears": F("number", derived=True, desc="From hireDate to now/termination."),
        "departmentId": F("string", ref="departments.departmentId"),
        "departmentName": F("string", derived=True),
        "jobId": F("string", ref="jobs.jobId"),
        "jobTitle": F("string", derived=True, desc="From jobs.title."),
        "jobLevel": F("int", derived=True, desc="From jobs.level (1..8)."),
        "positionId": F("string", required=False, ref="positions.positionId"),
        "managerId": F("string", required=False, ref="employees.employeeId",
                       desc="Real emp id; null ONLY for the CEO."),
        "managerName": F("string", required=False, derived=True),
        "isPeopleManager": F("bool", derived=True, desc="True if any employee has this managerId."),
        "directReportCount": F("int", derived=True),
        "workLocationId": F("string", ref="locations.locationId"),
        "workLocationName": F("string", derived=True),
        "country": F("string", desc="ISO-3166 alpha-2, e.g. 'US'."),
        "workMode": F("string", enum="workMode"),
        "timezone": F("string", required=False),
        "compensation": F("object", desc="{annualSalary(money), currency, payFrequency(enum payFrequency), "
                                         "bandId(ref compensation_bands.bandId), compaRatio(derived)}"),
        "workAuthorization": F("object", desc="{status(enum workAuthStatus), visaType, expirationDate}"),
        "ptoSnapshot": F("object", derived=True,
                         desc="Cache from leave ledger: {accrualDaysPerYear, usedDays, remainingDays, asOf}."),
        "benefitsSnapshot": F("object", derived=True,
                              desc="Cache from active election: {medicalPlanId+Name, dentalPlanId, visionPlanId, "
                                   "retirement401kPercent, employerMatchPercent}."),
        "engagementScore": F("number", required=False, desc="0-10 latest survey index."),
        "lastSurveyDate": F("date", required=False),
        "attritionRiskScore": F("number", required=False, derived=True, desc="0-1 from predictive model run."),
    },
    example={
        "id": "emp-0006", "employeeId": "emp-0006", "firstName": "Priya", "lastName": "Nair",
        "name": "Priya Nair", "preferredName": "Priya", "workEmail": "priya.nair@closedai.com",
        "personalEmail": "priya.nair@gmail.com", "phone": "+1-206-555-0142", "dateOfBirth": "1986-02-11",
        "gender": "female", "ethnicity": None, "employmentStatus": "active", "employmentType": "full_time",
        "flsaStatus": "exempt", "hireDate": "2020-06-01", "terminationDate": None, "tenureYears": 6.2,
        "departmentId": "dept-product", "departmentName": "Product", "jobId": "job-0007",
        "jobTitle": "Director of Product", "jobLevel": 6, "positionId": "pos-0007",
        "managerId": "emp-0001", "managerName": "Diego Moore", "isPeopleManager": True,
        "directReportCount": 6, "workLocationId": "loc-sea", "workLocationName": "Seattle, WA",
        "country": "US", "workMode": "hybrid", "timezone": "America/Los_Angeles",
        "compensation": {"annualSalary": 210000, "currency": "USD", "payFrequency": "biweekly",
                         "bandId": "band-PROD-6", "compaRatio": 0.98},
        "workAuthorization": {"status": "citizen", "visaType": None, "expirationDate": None},
        "ptoSnapshot": {"accrualDaysPerYear": 22, "usedDays": 6, "remainingDays": 16, "asOf": "2026-08-01"},
        "benefitsSnapshot": {"medicalPlanId": "plan-med-ppo", "medicalPlanName": "PPO Plus",
                             "dentalPlanId": "plan-den-std", "visionPlanId": "plan-vis-basic",
                             "retirement401kPercent": 6, "employerMatchPercent": 4},
        "engagementScore": 7.7, "lastSurveyDate": "2026-05-01", "attritionRiskScore": 0.18,
        "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
        "createdAt": "2020-06-01T09:00:00Z", "updatedAt": "2026-08-01T12:00:00Z",
    },
))

register(_spec(
    name="departments",
    partition_key="/id",
    domain="foundation",
    description="Hierarchical org units (company -> division -> department -> team).",
    unique_keys=[["/departmentId"]],
    seed="~1 root + 8-10 departments + a few teams. Fully connected via parentDepartmentId.",
    fields={
        "id": F("string"), "departmentId": F("string"),
        "name": F("string"),
        "levelType": F("string", enum="orgLevelType"),
        "parentDepartmentId": F("string", required=False, ref="departments.departmentId",
                                desc="null for the company root."),
        "leaderEmployeeId": F("string", ref="employees.employeeId"),
        "leaderName": F("string", derived=True),
        "costCenter": F("string", required=False),
        "layerLevel": F("int", derived=True, desc="Depth from root (root=1)."),
        "headcount": F("int", derived=True, desc="Employees in this unit + descendants."),
        "openHeadcount": F("int", derived=True, desc="Open positions in this unit."),
    },
    example={"id": "dept-product", "departmentId": "dept-product", "name": "Product",
             "levelType": "department", "parentDepartmentId": "dept-company",
             "leaderEmployeeId": "emp-0001", "leaderName": "Diego Moore", "costCenter": "CC-2000",
             "layerLevel": 2, "headcount": 42, "openHeadcount": 3, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2020-01-01T00:00:00Z",
             "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="locations",
    partition_key="/id",
    domain="foundation",
    description="Physical/virtual work locations catalog.",
    unique_keys=[["/locationId"]],
    seed="~6 locations incl. one 'remote-us'.",
    fields={
        "id": F("string"), "locationId": F("string"),
        "name": F("string"), "type": F("string", desc="office|remote|hybrid_hub"),
        "addressLine": F("string", required=False), "city": F("string", required=False),
        "state": F("string", required=False), "country": F("string"),
        "timezone": F("string"), "isHeadquarters": F("bool"),
    },
    example={"id": "loc-sea", "locationId": "loc-sea", "name": "Seattle HQ", "type": "office",
             "addressLine": "500 Pike St", "city": "Seattle", "state": "WA", "country": "US",
             "timezone": "America/Los_Angeles", "isHeadquarters": True, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2020-01-01T00:00:00Z",
             "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="job_families",
    partition_key="/id",
    domain="foundation",
    description="Top-level job families that group jobs and drive comp bands.",
    unique_keys=[["/jobFamilyId"]],
    seed="~10 families: ENG, PROD, DATA, DESIGN, SALES, CS, MKT, FIN, PEOPLE, OPS.",
    fields={
        "id": F("string"), "jobFamilyId": F("string"),
        "code": F("string", desc="Short code e.g. 'ENG' used by jobs.jobFamily & bands.jobFamily."),
        "name": F("string"), "description": F("string", required=False),
    },
    example={"id": "family-eng", "jobFamilyId": "family-eng", "code": "ENG",
             "name": "Engineering", "description": "Software engineering roles.",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2020-01-01T00:00:00Z", "updatedAt": "2020-01-01T00:00:00Z"},
))

register(_spec(
    name="jobs",
    partition_key="/jobFamily",
    domain="foundation",
    description="Catalog of roles. Employees & requisitions reference a jobId.",
    unique_keys=[["/jobId"]],
    seed="~60 jobs across families and levels 1..8.",
    fields={
        "id": F("string"), "jobId": F("string"),
        "title": F("string"),
        "jobFamily": F("string", ref="job_families.code", desc="Family code, e.g. 'ENG'."),
        "level": F("int", desc="1..8; 1-4 IC, 5 manager, 6 director, 7 VP/CxO, 8 CEO."),
        "flsaStatus": F("string", enum="flsaStatus"),
        "isManagerJob": F("bool"),
        "description": F("string", required=False),
        "requiredSkillIds": F("array<string>", required=False, ref="skills_taxonomy.skillId"),
    },
    exclude_paths=["/description/?"],
    example={"id": "job-0007", "jobId": "job-0007", "title": "Director of Product",
             "jobFamily": "PROD", "level": 6, "flsaStatus": "exempt", "isManagerJob": True,
             "description": "Leads product management for a business line.",
             "requiredSkillIds": ["skill-product-strategy", "skill-roadmapping"],
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2020-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="compensation_bands",
    partition_key="/jobFamily",
    domain="foundation",
    description="Salary bands per job family + level. Employee salary must fit its band.",
    unique_keys=[["/bandId"]],
    seed="One band per (family, level) that jobs actually use (~40 bands).",
    fields={
        "id": F("string"), "bandId": F("string"),
        "jobFamily": F("string", ref="job_families.code"),
        "level": F("int"), "currency": F("string"),
        "min": F("money"), "mid": F("money"), "max": F("money"),
        "geoZone": F("string", desc="e.g. 'US-national'."),
    },
    example={"id": "band-PROD-6", "bandId": "band-PROD-6", "jobFamily": "PROD", "level": 6,
             "currency": "USD", "min": 185000, "mid": 215000, "max": 250000, "geoZone": "US-national",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2020-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="positions",
    partition_key="/departmentId",
    domain="foundation",
    description="Budgeted headcount slots (filled or open). Backbone for workforce planning.",
    unique_keys=[["/positionId"]],
    seed="One position per employee (filled) + ~15 open positions tied to requisitions.",
    fields={
        "id": F("string"), "positionId": F("string"),
        "jobId": F("string", ref="jobs.jobId"),
        "title": F("string", derived=True, desc="From job."),
        "departmentId": F("string", ref="departments.departmentId"),
        "status": F("string", desc="filled|open|frozen"),
        "incumbentEmployeeId": F("string", required=False, ref="employees.employeeId",
                                 desc="null when open/frozen."),
        "requisitionId": F("string", required=False, ref="job_requisitions.requisitionId",
                           desc="Set when open & actively hiring."),
        "budgetedFte": F("number"), "workLocationId": F("string", ref="locations.locationId"),
    },
    example={"id": "pos-0007", "positionId": "pos-0007", "jobId": "job-0007",
             "title": "Director of Product", "departmentId": "dept-product", "status": "filled",
             "incumbentEmployeeId": "emp-0006", "requisitionId": None, "budgetedFte": 1.0,
             "workLocationId": "loc-sea", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2020-06-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))


# ===========================================================================
# DOMAIN 2 — RECRUITING / ATS  (Candidate -> Application -> Offer -> Employee)
# ===========================================================================

register(_spec(
    name="job_requisitions",
    partition_key="/departmentId",
    domain="recruiting",
    description="Open roles being hired for. Ties to a job, department, hiring manager.",
    unique_keys=[["/requisitionId"]],
    seed="~15 open reqs across departments, each linked to an open position.",
    fields={
        "id": F("string"), "requisitionId": F("string"),
        "title": F("string"), "jobId": F("string", ref="jobs.jobId"),
        "departmentId": F("string", ref="departments.departmentId"),
        "positionId": F("string", required=False, ref="positions.positionId"),
        "hiringManagerId": F("string", ref="employees.employeeId"),
        "recruiterId": F("string", ref="employees.employeeId"),
        "workLocationId": F("string", ref="locations.locationId"),
        "employmentType": F("string", enum="employmentType"),
        "headcount": F("int"), "filledCount": F("int", derived=True),
        "status": F("string", enum="requisitionStatus"),
        "bandId": F("string", ref="compensation_bands.bandId"),
        "salaryRangeMin": F("money"), "salaryRangeMax": F("money"),
        "openDate": F("date"), "targetFillDate": F("date", required=False),
        "daysOpen": F("int", derived=True),
    },
    example={"id": "req-0015", "requisitionId": "req-0015", "title": "Senior Backend Engineer",
             "jobId": "job-0021", "departmentId": "dept-eng", "positionId": "pos-0210",
             "hiringManagerId": "emp-0006", "recruiterId": "emp-0044", "workLocationId": "loc-sea",
             "employmentType": "full_time", "headcount": 2, "filledCount": 0, "status": "open",
             "bandId": "band-ENG-4", "salaryRangeMin": 150000, "salaryRangeMax": 190000,
             "openDate": "2026-07-01", "targetFillDate": "2026-09-15", "daysOpen": 49,
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="candidates",
    partition_key="/id",
    domain="recruiting",
    description="People in the talent pool / applying. Becomes an employee on offer accept.",
    unique_keys=[["/candidateId"]],
    seed="~90 candidates; ~10 later map to newest hires (candidateId on employee via applications).",
    fields={
        "id": F("string"), "candidateId": F("string"),
        "firstName": F("string"), "lastName": F("string"), "name": F("string", derived=True),
        "email": F("string"), "phone": F("string", required=False),
        "resumeUrl": F("string", required=False),
        "source": F("string", desc="inbound|referral|sourced|agency|event"),
        "sourceChannel": F("string", required=False, desc="LinkedIn|Indeed|referral name|..."),
        "referrerEmployeeId": F("string", required=False, ref="employees.employeeId"),
        "talentPoolTags": F("array<string>", required=False),
        "currentTitle": F("string", required=False), "currentCompany": F("string", required=False),
        "location": F("string", required=False),
        "consentStatus": F("string", enum="consentStatus", desc="Data-processing consent for recruiting."),
    },
    example={"id": "cand-0088", "candidateId": "cand-0088", "firstName": "Alex", "lastName": "Rivera",
             "name": "Alex Rivera", "email": "alex.rivera@example.com", "phone": "+1-415-555-0199",
             "resumeUrl": "blob://resumes/cand-0088.pdf", "source": "referral", "sourceChannel": "emp-0031",
             "referrerEmployeeId": "emp-0031", "talentPoolTags": ["backend", "python"],
             "currentTitle": "Backend Engineer", "currentCompany": "Acme", "location": "San Francisco, CA",
             "consentStatus": "granted", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-05T00:00:00Z", "updatedAt": "2026-07-20T00:00:00Z"},
))

register(_spec(
    name="applications",
    partition_key="/requisitionId",
    domain="recruiting",
    description="A candidate's application to a requisition; moves through stages.",
    unique_keys=[["/applicationId"]],
    seed="~130 applications across reqs; realistic stage funnel + dispositions.",
    fields={
        "id": F("string"), "applicationId": F("string"),
        "candidateId": F("string", ref="candidates.candidateId"),
        "requisitionId": F("string", ref="job_requisitions.requisitionId"),
        "stage": F("string", enum="applicationStage"),
        "status": F("string", desc="active|rejected|withdrawn|hired"),
        "appliedDate": F("date"),
        "dispositionReason": F("string", required=False),
        "score": F("number", required=False, desc="0-100 overall screen score."),
        "hiredEmployeeId": F("string", required=False, ref="employees.employeeId",
                             desc="Set when stage=hired -> the created employee."),
    },
    example={"id": "app-0140", "applicationId": "app-0140", "candidateId": "cand-0088",
             "requisitionId": "req-0015", "stage": "onsite", "status": "active",
             "appliedDate": "2026-07-06", "dispositionReason": None, "score": 82,
             "hiredEmployeeId": None, "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-06T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="interviews",
    partition_key="/applicationId",
    domain="recruiting",
    description="Interviews for an application, with embedded scorecards.",
    unique_keys=[["/interviewId"]],
    seed="~1-4 interviews per advanced application.",
    fields={
        "id": F("string"), "interviewId": F("string"),
        "applicationId": F("string", ref="applications.applicationId"),
        "requisitionId": F("string", ref="job_requisitions.requisitionId",
                          desc="Partition alignment with the recruiting funnel."),
        "type": F("string", enum="interviewType"),
        "scheduledAt": F("datetime"), "durationMinutes": F("int"),
        "interviewerIds": F("array<string>", ref="employees.employeeId"),
        "status": F("string", desc="scheduled|completed|cancelled|no_show"),
        "scorecards": F("array<object>", required=False,
                        desc="[{interviewerId, competency, rating(1-5), notes}]"),
        "overallRecommendation": F("string", required=False, enum="recommendation"),
    },
    example={"id": "intv-0301", "interviewId": "intv-0301", "applicationId": "app-0140",
             "type": "technical", "scheduledAt": "2026-07-25T17:00:00Z", "durationMinutes": 60,
             "requisitionId": "req-0015", "interviewerIds": ["emp-0021", "emp-0033"], "status": "completed",
             "scorecards": [{"interviewerId": "emp-0021", "competency": "coding", "rating": 4,
                             "notes": "Strong."}],
             "overallRecommendation": "yes", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-20T00:00:00Z", "updatedAt": "2026-07-25T18:00:00Z"},
))

register(_spec(
    name="offers",
    partition_key="/applicationId",
    domain="recruiting",
    description="Offer for an application; on accept the populator creates the employee.",
    unique_keys=[["/offerId"]],
    seed="~10 offers in mixed statuses; ~6 accepted -> newest employees + onboarding.",
    fields={
        "id": F("string"), "offerId": F("string"),
        "applicationId": F("string", ref="applications.applicationId"),
        "requisitionId": F("string", ref="job_requisitions.requisitionId"),
        "candidateId": F("string", ref="candidates.candidateId"),
        "baseSalary": F("money"), "currency": F("string"),
        "signOnBonus": F("money", required=False), "targetBonusPercent": F("number", required=False),
        "equityShares": F("int", required=False),
        "startDate": F("date"), "status": F("string", enum="offerStatus"),
        "extendedDate": F("date", required=False), "expiryDate": F("date", required=False),
        "decisionDate": F("date", required=False),
        "approverIds": F("array<string>", required=False, ref="employees.employeeId"),
    },
    example={"id": "offer-0021", "offerId": "offer-0021", "applicationId": "app-0140",
             "requisitionId": "req-0015", "candidateId": "cand-0088", "baseSalary": 175000,
             "currency": "USD", "signOnBonus": 15000, "targetBonusPercent": 10, "equityShares": 2000,
             "startDate": "2026-09-01", "status": "accepted", "extendedDate": "2026-08-05",
             "expiryDate": "2026-08-15", "decisionDate": "2026-08-08", "approverIds": ["emp-0006", "emp-0001"],
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-08-05T00:00:00Z", "updatedAt": "2026-08-08T00:00:00Z"},
))

# ---- Lifecycle: onboarding / offboarding / exit ----

register(_spec(
    name="onboarding_checklists",
    partition_key="/employeeId",
    domain="lifecycle",
    description="Per-hire onboarding plan + tasks. employeeId is a REAL FK (fixes old orphans).",
    unique_keys=[["/checklistId"]],
    seed="~15 recent hires; realistic task mix and statuses.",
    fields={
        "id": F("string"), "checklistId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "employeeName": F("string", derived=True),
        "jobId": F("string", ref="jobs.jobId"),
        "departmentId": F("string", ref="departments.departmentId"),
        "startDate": F("date"), "status": F("string", enum="checklistStatus"),
        "hrOwnerId": F("string", ref="employees.employeeId"),
        "managerId": F("string", ref="employees.employeeId"),
        "tasks": F("array<object>", desc="[{key, label, status(enum taskStatus), dueDate, completedDate}]"),
        "percentComplete": F("number", derived=True),
    },
    example={"id": "onb-0009", "checklistId": "onb-0009", "employeeId": "emp-0248",
             "employeeName": "Alex Rivera", "jobId": "job-0021", "departmentId": "dept-eng",
             "startDate": "2026-09-01", "status": "in_progress", "hrOwnerId": "emp-0009",
             "managerId": "emp-0006",
             "tasks": [{"key": "i9", "label": "I-9 Verification", "status": "pending",
                        "dueDate": "2026-09-04", "completedDate": None}],
             "percentComplete": 0.0, "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-08-10T00:00:00Z", "updatedAt": "2026-08-10T00:00:00Z"},
))

register(_spec(
    name="offboarding_checklists",
    partition_key="/employeeId",
    domain="lifecycle",
    description="Separation plan + tasks for departing employees.",
    unique_keys=[["/checklistId"]],
    seed="~6 recent departures (mix voluntary/involuntary).",
    fields={
        "id": F("string"), "checklistId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "employeeName": F("string", derived=True),
        "separationType": F("string", enum="separationType"),
        "reason": F("string", required=False), "lastDay": F("date"),
        "status": F("string", enum="checklistStatus"),
        "hrOwnerId": F("string", ref="employees.employeeId"),
        "tasks": F("array<object>", desc="[{key, label, status, dueDate, completedDate}] e.g. access_revoke, "
                                         "equipment_return, final_pay, knowledge_transfer."),
        "rehireEligible": F("bool", required=False),
    },
    example={"id": "off-0003", "checklistId": "off-0003", "employeeId": "emp-0112",
             "employeeName": "Jordan Lee", "separationType": "voluntary", "reason": "New opportunity",
             "lastDay": "2026-08-29", "status": "in_progress", "hrOwnerId": "emp-0009",
             "tasks": [{"key": "access_revoke", "label": "Revoke system access", "status": "pending",
                        "dueDate": "2026-08-29", "completedDate": None}],
             "rehireEligible": True, "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-08-15T00:00:00Z", "updatedAt": "2026-08-15T00:00:00Z"},
))

register(_spec(
    name="exit_interviews",
    partition_key="/employeeId",
    domain="lifecycle",
    description="Exit interview responses + themes for departed employees.",
    unique_keys=[["/exitInterviewId"]],
    seed="One per completed offboarding.",
    fields={
        "id": F("string"), "exitInterviewId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "conductedDate": F("date"), "conductedById": F("string", ref="employees.employeeId"),
        "responses": F("array<object>", desc="[{question, answer, sentiment}]"),
        "primaryReason": F("string"), "themes": F("array<string>"),
        "wouldRecommend": F("bool", required=False), "rehireEligible": F("bool"),
    },
    example={"id": "exit-0003", "exitInterviewId": "exit-0003", "employeeId": "emp-0112",
             "conductedDate": "2026-08-28", "conductedById": "emp-0009",
             "responses": [{"question": "Primary reason for leaving?", "answer": "Career growth",
                            "sentiment": "neutral"}],
             "primaryReason": "career_growth", "themes": ["growth", "compensation"],
             "wouldRecommend": True, "rehireEligible": True, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-08-28T00:00:00Z",
             "updatedAt": "2026-08-28T00:00:00Z"},
))


# ===========================================================================
# DOMAIN 3 — COMPENSATION, PAYROLL & BENEFITS
# ===========================================================================

register(_spec(
    name="pay_groups",
    partition_key="/id",
    domain="payroll",
    description="Pay calendars/groups that runs belong to.",
    unique_keys=[["/payGroupId"]],
    seed="~2 groups: US-biweekly (most), US-monthly (execs).",
    fields={
        "id": F("string"), "payGroupId": F("string"),
        "name": F("string"), "frequency": F("string", enum="payFrequency"),
        "periodsPerYear": F("int"), "currency": F("string"), "country": F("string"),
    },
    example={"id": "pg-us-biweekly", "payGroupId": "pg-us-biweekly", "name": "US Biweekly",
             "frequency": "biweekly", "periodsPerYear": 26, "currency": "USD", "country": "US",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2020-01-01T00:00:00Z", "updatedAt": "2020-01-01T00:00:00Z"},
))

register(_spec(
    name="payroll_runs",
    partition_key="/payGroupId",
    domain="payroll",
    description="A processed payroll cycle for a pay group.",
    unique_keys=[["/payRunId"]],
    seed="~6 recent monthly/biweekly runs, status=processed/paid.",
    fields={
        "id": F("string"), "payRunId": F("string"),
        "payGroupId": F("string", ref="pay_groups.payGroupId"),
        "periodStart": F("date"), "periodEnd": F("date"), "payDate": F("date"),
        "status": F("string", enum="payrollStatus"),
        "employeeCount": F("int", derived=True), "grossTotal": F("money", derived=True),
        "netTotal": F("money", derived=True), "taxTotal": F("money", derived=True),
        "currency": F("string"), "approvedById": F("string", required=False, ref="employees.employeeId"),
    },
    example={"id": "run-2026-08b", "payRunId": "run-2026-08b", "payGroupId": "pg-us-biweekly",
             "periodStart": "2026-08-01", "periodEnd": "2026-08-15", "payDate": "2026-08-20",
             "status": "paid", "employeeCount": 230, "grossTotal": 934210.55, "netTotal": 651900.10,
             "taxTotal": 210300.00, "currency": "USD", "approvedById": "emp-0009", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-08-16T00:00:00Z",
             "updatedAt": "2026-08-20T00:00:00Z"},
))

register(_spec(
    name="pay_statements",
    partition_key="/employeeId",
    domain="payroll",
    description="Per-employee payslip for a run, with embedded line items.",
    unique_keys=[["/payStatementId"]],
    seed="One per active employee per run (latest 1-2 runs is enough).",
    fields={
        "id": F("string"), "payStatementId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "payRunId": F("string", ref="payroll_runs.payRunId"),
        "grossPay": F("money"), "netPay": F("money"), "currency": F("string"),
        "lineItems": F("array<object>", desc="[{type(enum payLineType), code, amount, hours?}]"),
        "ytdGross": F("money"), "ytdTax": F("money"), "ytdNet": F("money"),
    },
    example={"id": "pay-0777", "payStatementId": "pay-0777", "employeeId": "emp-0031",
             "payRunId": "run-2026-08b", "grossPay": 3461.54, "netPay": 2450.10, "currency": "USD",
             "lineItems": [{"type": "earning", "code": "base", "amount": 3461.54},
                           {"type": "tax", "code": "federal", "amount": -620.00},
                           {"type": "deduction", "code": "401k", "amount": -207.69},
                           {"type": "benefit", "code": "medical", "amount": -60.00}],
             "ytdGross": 55384.64, "ytdTax": 9920.00, "ytdNet": 39201.60, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-08-20T00:00:00Z",
             "updatedAt": "2026-08-20T00:00:00Z"},
))

register(_spec(
    name="compensation_records",
    partition_key="/employeeId",
    domain="payroll",
    description="Compensation change history (hire, merit, promotion, market adj).",
    unique_keys=[["/compRecordId"]],
    seed="1-3 records per employee forming a coherent salary history within bands.",
    fields={
        "id": F("string"), "compRecordId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "effectiveDate": F("date"),
        "changeReason": F("string", desc="hire|merit|promotion|market_adjustment|demotion"),
        "baseSalary": F("money"), "currency": F("string"), "payFrequency": F("string", enum="payFrequency"),
        "bandId": F("string", ref="compensation_bands.bandId"),
        "compaRatio": F("number", derived=True),
        "previousSalary": F("money", required=False), "percentChange": F("number", derived=True),
    },
    example={"id": "comp-0501", "compRecordId": "comp-0501", "employeeId": "emp-0031",
             "effectiveDate": "2026-01-01", "changeReason": "merit", "baseSalary": 90000,
             "currency": "USD", "payFrequency": "biweekly", "bandId": "band-ENG-3", "compaRatio": 0.95,
             "previousSalary": 85000, "percentChange": 5.9, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z",
             "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="bonus_payouts",
    partition_key="/employeeId",
    domain="payroll",
    description="Bonus/incentive payouts per employee per period.",
    unique_keys=[["/payoutId"]],
    seed="Annual bonus payout for eligible employees for the last cycle.",
    fields={
        "id": F("string"), "payoutId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "planName": F("string", desc="e.g. 'FY25 Annual Bonus'."),
        "period": F("string"), "targetAmount": F("money"), "actualAmount": F("money"),
        "targetPercent": F("number"), "payoutPercent": F("number"),
        "status": F("string", desc="calculated|approved|paid"), "payDate": F("date", required=False),
    },
    example={"id": "bonus-0301", "payoutId": "bonus-0301", "employeeId": "emp-0031",
             "planName": "FY25 Annual Bonus", "period": "FY2025", "targetAmount": 9000,
             "actualAmount": 8100, "targetPercent": 10, "payoutPercent": 90, "status": "paid",
             "payDate": "2026-03-15", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-03-01T00:00:00Z", "updatedAt": "2026-03-15T00:00:00Z"},
))

register(_spec(
    name="equity_grants",
    partition_key="/employeeId",
    domain="payroll",
    description="Equity grants and vesting schedules.",
    unique_keys=[["/grantId"]],
    seed="Grants for ~exec + senior population; standard 4yr/1yr-cliff schedules.",
    fields={
        "id": F("string"), "grantId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "grantType": F("string", desc="option|rsu|espp"),
        "shares": F("int"), "strikePrice": F("number", required=False),
        "grantDate": F("date"), "vestStartDate": F("date"),
        "vestingSchedule": F("string", desc="e.g. '4yr-monthly-1yr-cliff'."),
        "vestedShares": F("int", derived=True), "status": F("string", desc="active|fully_vested|cancelled"),
    },
    example={"id": "grant-0044", "grantId": "grant-0044", "employeeId": "emp-0006",
             "grantType": "rsu", "shares": 8000, "strikePrice": None, "grantDate": "2020-06-01",
             "vestStartDate": "2020-06-01", "vestingSchedule": "4yr-quarterly-1yr-cliff",
             "vestedShares": 8000, "status": "fully_vested", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2020-06-01T00:00:00Z",
             "updatedAt": "2026-08-01T00:00:00Z"},
))

# ---- Benefits ----

register(_spec(
    name="benefits_plans",
    partition_key="/planType",
    domain="benefits",
    description="Catalog of benefit plans employees can elect.",
    unique_keys=[["/planId"]],
    seed="~10 plans across medical/dental/vision/401k/hsa/fsa/life/disability.",
    fields={
        "id": F("string"), "planId": F("string"),
        "planName": F("string"), "planType": F("string", enum="planType"),
        "carrier": F("string"),
        "monthlyPremiumEmployee": F("money"), "monthlyPremiumDependent": F("money", required=False),
        "deductible": F("money", required=False), "outOfPocketMax": F("money", required=False),
        "companyContributionPercent": F("number", required=False), "currency": F("string"),
        "eligibilityRule": F("string", required=False, desc="e.g. 'full_time, >30 days'."),
    },
    example={"id": "plan-med-ppo", "planId": "plan-med-ppo", "planName": "PPO Plus",
             "planType": "medical", "carrier": "BlueCross", "monthlyPremiumEmployee": 120,
             "monthlyPremiumDependent": 300, "deductible": 1000, "outOfPocketMax": 4000,
             "companyContributionPercent": 80, "currency": "USD", "eligibilityRule": "full_time",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="benefits_elections",
    partition_key="/employeeId",
    domain="benefits",
    description="An employee's elected benefits (with embedded dependents). Matches employee snapshot.",
    unique_keys=[["/electionId"]],
    seed="One active election per active employee; ~40% with dependents.",
    fields={
        "id": F("string"), "electionId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "employeeName": F("string", derived=True),
        "planElections": F("array<object>",
                           desc="[{planId(ref benefits_plans.planId), planType, coverageLevel(enum), "
                                "monthlyEmployeeCost, effectiveDate}]"),
        "retirement401kPercent": F("number"), "employerMatchPercent": F("number"),
        "dependents": F("array<object>", required=False,
                        desc="[{name, relationship, dateOfBirth}]"),
        "status": F("string", desc="active|ended"), "effectiveDate": F("date"),
        "endDate": F("date", required=False),
    },
    example={"id": "elec-0031", "electionId": "elec-0031", "employeeId": "emp-0031",
             "employeeName": "Mia Brown",
             "planElections": [{"planId": "plan-med-ppo", "planType": "medical",
                                "coverageLevel": "employee_children", "monthlyEmployeeCost": 420,
                                "effectiveDate": "2026-01-01"}],
             "retirement401kPercent": 6, "employerMatchPercent": 4,
             "dependents": [{"name": "Sam Brown", "relationship": "child", "dateOfBirth": "2018-05-02"}],
             "status": "active", "effectiveDate": "2026-01-01", "endDate": None, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z",
             "updatedAt": "2026-01-01T00:00:00Z"},
))

# ---- Time & leave ----

register(_spec(
    name="leave_policies",
    partition_key="/id",
    domain="time_leave",
    description="Accrual rules per leave type. Numbers MUST match the policy doc text.",
    unique_keys=[["/leavePolicyId"]],
    seed="pto(tenure tiers 15/18/22), sick(10), parental, fmla, bereavement, jury_duty.",
    fields={
        "id": F("string"), "leavePolicyId": F("string"),
        "leaveType": F("string", enum="leaveType"),
        "accrualRule": F("string", desc="Human-readable accrual, e.g. tenure tiers."),
        "accrualTiers": F("array<object>", required=False,
                          desc="[{minTenureYears, maxTenureYears, daysPerYear}]"),
        "maxCarryoverDays": F("number", required=False), "paid": F("bool"),
        "jurisdiction": F("string"), "policyId": F("string", ref="policies.policyId"),
    },
    example={"id": "lp-pto", "leavePolicyId": "lp-pto", "leaveType": "pto",
             "accrualRule": "15 days (<2y), 18 (2-5y), 22 (5y+)",
             "accrualTiers": [{"minTenureYears": 0, "maxTenureYears": 2, "daysPerYear": 15},
                              {"minTenureYears": 2, "maxTenureYears": 5, "daysPerYear": 18},
                              {"minTenureYears": 5, "maxTenureYears": 99, "daysPerYear": 22}],
             "maxCarryoverDays": 5, "paid": True, "jurisdiction": "US", "policyId": "policy-pto",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="leave_requests",
    partition_key="/employeeId",
    domain="time_leave",
    description="Leave ledger. Source of truth for PTO usage -> drives balances + snapshot.",
    unique_keys=[["/leaveRequestId"]],
    seed="~200 requests across the year; statuses realistic; all employeeIds real.",
    fields={
        "id": F("string"), "leaveRequestId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "employeeName": F("string", derived=True),
        "leaveType": F("string", enum="leaveType"),
        "startDate": F("date"), "endDate": F("date"),
        "businessDays": F("number", derived=True, desc="Excludes weekends/holidays."),
        "status": F("string", enum="leaveStatus"),
        "approverId": F("string", required=False, ref="employees.employeeId"),
        "requestedDate": F("date"), "reason": F("string", required=False),
    },
    example={"id": "leave-0042", "leaveRequestId": "leave-0042", "employeeId": "emp-0031",
             "employeeName": "Mia Brown", "leaveType": "pto", "startDate": "2026-08-10",
             "endDate": "2026-08-14", "businessDays": 5, "status": "approved", "approverId": "emp-0006",
             "requestedDate": "2026-07-20", "reason": None, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-07-20T00:00:00Z",
             "updatedAt": "2026-07-21T00:00:00Z"},
))

register(_spec(
    name="leave_balances",
    partition_key="/employeeId",
    domain="time_leave",
    description="Per employee x leaveType x year rollup, derived from leave_requests + policy.",
    unique_keys=[["/id"]],
    seed="pto + sick balance rows per active employee for 2026.",
    fields={
        "id": F("string", desc="'bal-<employeeId>-<leaveType>-<year>'."),
        "employeeId": F("string", ref="employees.employeeId"),
        "leaveType": F("string", enum="leaveType"), "year": F("int"),
        "accruedDays": F("number", derived=True), "usedDays": F("number", derived=True),
        "pendingDays": F("number", derived=True), "availableDays": F("number", derived=True),
        "asOf": F("date"),
    },
    example={"id": "bal-emp-0031-pto-2026", "employeeId": "emp-0031", "leaveType": "pto",
             "year": 2026, "accruedDays": 18, "usedDays": 5, "pendingDays": 0, "availableDays": 13,
             "asOf": "2026-08-01", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="timesheets",
    partition_key="/employeeId",
    domain="time_leave",
    description="Per-period timesheet for non-exempt employees, with embedded entries.",
    unique_keys=[["/timesheetId"]],
    seed="Recent 1-2 periods for non-exempt population only.",
    fields={
        "id": F("string"), "timesheetId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "payPeriodStart": F("date"), "payPeriodEnd": F("date"),
        "entries": F("array<object>", desc="[{date, clockIn, clockOut, breakMinutes, hours}]"),
        "regularHours": F("number", derived=True), "overtimeHours": F("number", derived=True),
        "status": F("string", desc="draft|submitted|approved|rejected"),
        "approverId": F("string", required=False, ref="employees.employeeId"),
    },
    example={"id": "ts-0140", "timesheetId": "ts-0140", "employeeId": "emp-0180",
             "payPeriodStart": "2026-08-01", "payPeriodEnd": "2026-08-15",
             "entries": [{"date": "2026-08-01", "clockIn": "09:00", "clockOut": "17:30",
                          "breakMinutes": 30, "hours": 8.0}],
             "regularHours": 80.0, "overtimeHours": 2.5, "status": "approved", "approverId": "emp-0033",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-08-16T00:00:00Z", "updatedAt": "2026-08-17T00:00:00Z"},
))


# ===========================================================================
# DOMAIN 4 — PERFORMANCE & TALENT MANAGEMENT
# ===========================================================================

register(_spec(
    name="review_cycles",
    partition_key="/id",
    domain="performance",
    description="Performance review cycles.",
    unique_keys=[["/cycleId"]],
    seed="~3 cycles: 2025 annual (closed), 2026 mid-year (shared), 2026 annual (active).",
    fields={
        "id": F("string"), "cycleId": F("string"),
        "name": F("string"), "type": F("string", enum="reviewCycleType"),
        "startDate": F("date"), "endDate": F("date"),
        "status": F("string", desc="upcoming|active|calibration|closed"),
    },
    example={"id": "cycle-2026-h1", "cycleId": "cycle-2026-h1", "name": "2026 Mid-Year",
             "type": "mid_year", "startDate": "2026-06-01", "endDate": "2026-06-30",
             "status": "closed", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-05-01T00:00:00Z", "updatedAt": "2026-07-01T00:00:00Z"},
))

register(_spec(
    name="performance_reviews",
    partition_key="/employeeId",
    domain="performance",
    description="A review of an employee within a cycle.",
    unique_keys=[["/reviewId"]],
    seed="One per active employee for the last closed cycle; realistic rating distribution.",
    fields={
        "id": F("string"), "reviewId": F("string"),
        "cycleId": F("string", ref="review_cycles.cycleId"),
        "employeeId": F("string", ref="employees.employeeId"),
        "reviewerId": F("string", ref="employees.employeeId"),
        "overallRating": F("int", desc="1..5 (1 below, 3 meets, 5 exceeds)."),
        "calibratedRating": F("int", required=False),
        "summary": F("string"), "strengths": F("array<string>", required=False),
        "developmentAreas": F("array<string>", required=False),
        "status": F("string", enum="reviewStatus"),
    },
    exclude_paths=["/summary/?"],
    example={"id": "rev-0400", "reviewId": "rev-0400", "cycleId": "cycle-2026-h1",
             "employeeId": "emp-0031", "reviewerId": "emp-0006", "overallRating": 4,
             "calibratedRating": 4, "summary": "Consistently strong delivery.",
             "strengths": ["ownership", "collaboration"], "developmentAreas": ["strategic influence"],
             "status": "shared", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-06-15T00:00:00Z", "updatedAt": "2026-07-01T00:00:00Z"},
))

register(_spec(
    name="goals",
    partition_key="/employeeId",
    domain="performance",
    description="Employee goals/OKRs, optionally cascaded via parentGoalId.",
    unique_keys=[["/goalId"]],
    seed="~2-4 goals per active employee for the current cycle.",
    fields={
        "id": F("string"), "goalId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "cycleId": F("string", ref="review_cycles.cycleId"),
        "title": F("string"), "description": F("string", required=False),
        "weight": F("number", required=False), "target": F("string", required=False),
        "progress": F("number", desc="0-100."), "status": F("string", enum="goalStatus"),
        "parentGoalId": F("string", required=False, ref="goals.goalId"),
    },
    example={"id": "goal-0900", "goalId": "goal-0900", "employeeId": "emp-0031",
             "cycleId": "cycle-2026-h1", "title": "Ship billing v2", "description": "GA by Q3",
             "weight": 40, "target": "GA by 2026-09-30", "progress": 70, "status": "active",
             "parentGoalId": "goal-0100", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-06-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="feedback",
    partition_key="/revieweeId",
    domain="performance",
    description="360 / continuous feedback entries.",
    unique_keys=[["/feedbackId"]],
    seed="Several 360 entries for employees reviewed in the last cycle.",
    fields={
        "id": F("string"), "feedbackId": F("string"),
        "revieweeId": F("string", ref="employees.employeeId"),
        "employeeId": F("string", ref="employees.employeeId", derived=True,
                       desc="== revieweeId; partition alignment with employee_records."),
        "reviewerId": F("string", ref="employees.employeeId"),
        "cycleId": F("string", required=False, ref="review_cycles.cycleId"),
        "relationship": F("string", enum="feedbackRelationship"),
        "competencyScores": F("array<object>", required=False, desc="[{competency, score(1-5)}]"),
        "comments": F("string", required=False), "submittedDate": F("date"),
    },
    example={"id": "fb-0210", "feedbackId": "fb-0210", "revieweeId": "emp-0031",
             "employeeId": "emp-0031", "reviewerId": "emp-0044", "cycleId": "cycle-2026-h1",
             "relationship": "peer",
             "competencyScores": [{"competency": "collaboration", "score": 5}],
             "comments": "Great partner across teams.", "submittedDate": "2026-06-20",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-06-20T00:00:00Z", "updatedAt": "2026-06-20T00:00:00Z"},
))

register(_spec(
    name="pips",
    partition_key="/employeeId",
    domain="performance",
    description="Performance improvement plans.",
    unique_keys=[["/pipId"]],
    seed="~3-5 active/closed PIPs tied to low ratings.",
    fields={
        "id": F("string"), "pipId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "ownerId": F("string", ref="employees.employeeId", desc="Manager/HRBP running it."),
        "startDate": F("date"), "endDate": F("date"),
        "issues": F("array<string>"), "goals": F("array<object>", desc="[{goal, dueDate, status}]"),
        "checkInDates": F("array<date>", required=False),
        "outcome": F("string", enum="pipOutcome"), "linkedCaseId": F("string", required=False, ref="er_cases.caseId"),
    },
    example={"id": "pip-0007", "pipId": "pip-0007", "employeeId": "emp-0155", "ownerId": "emp-0033",
             "startDate": "2026-07-01", "endDate": "2026-09-30", "issues": ["missed deadlines"],
             "goals": [{"goal": "Deliver sprint commitments", "dueDate": "2026-08-15", "status": "in_progress"}],
             "checkInDates": ["2026-07-15", "2026-08-15"], "outcome": "in_progress", "linkedCaseId": None,
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="recognition_awards",
    partition_key="/employeeId",
    domain="performance",
    description="Peer/manager recognition + spot bonuses.",
    unique_keys=[["/awardId"]],
    seed="~50 recognitions spread across the org.",
    fields={
        "id": F("string"), "awardId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "grantedById": F("string", ref="employees.employeeId"),
        "type": F("string", desc="spot_bonus|peer_kudos|milestone|value_award"),
        "points": F("int", required=False), "amount": F("money", required=False),
        "reason": F("string"), "grantedDate": F("date"),
    },
    example={"id": "award-0055", "awardId": "award-0055", "employeeId": "emp-0031",
             "grantedById": "emp-0006", "type": "spot_bonus", "points": None, "amount": 500,
             "reason": "Saved the launch.", "grantedDate": "2026-07-30", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-07-30T00:00:00Z",
             "updatedAt": "2026-07-30T00:00:00Z"},
))

register(_spec(
    name="succession_plans",
    partition_key="/positionId",
    domain="talent",
    description="Succession bench for critical positions.",
    unique_keys=[["/successionPlanId"]],
    seed="Plans for exec + director positions.",
    fields={
        "id": F("string"), "successionPlanId": F("string"),
        "positionId": F("string", ref="positions.positionId"),
        "incumbentEmployeeId": F("string", required=False, ref="employees.employeeId"),
        "readyNowIds": F("array<string>", required=False, ref="employees.employeeId"),
        "ready1YearIds": F("array<string>", required=False, ref="employees.employeeId"),
        "ready3YearIds": F("array<string>", required=False, ref="employees.employeeId"),
        "riskLevel": F("string", desc="low|medium|high (vacancy risk)."),
    },
    example={"id": "succ-0007", "successionPlanId": "succ-0007", "positionId": "pos-0007",
             "incumbentEmployeeId": "emp-0006", "readyNowIds": ["emp-0031"], "ready1YearIds": ["emp-0044"],
             "ready3YearIds": [], "riskLevel": "medium", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-06-01T00:00:00Z",
             "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="internal_mobility",
    partition_key="/employeeId",
    domain="talent",
    description="Internal transfer/promotion requests.",
    unique_keys=[["/mobilityId"]],
    seed="~10 recent internal moves/requests.",
    fields={
        "id": F("string"), "mobilityId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "fromPositionId": F("string", ref="positions.positionId"),
        "targetRequisitionId": F("string", required=False, ref="job_requisitions.requisitionId"),
        "targetPositionId": F("string", required=False, ref="positions.positionId"),
        "type": F("string", desc="promotion|lateral|transfer"),
        "status": F("string", desc="requested|in_review|approved|rejected|completed"),
        "requestedDate": F("date"), "effectiveDate": F("date", required=False),
    },
    example={"id": "mob-0003", "mobilityId": "mob-0003", "employeeId": "emp-0044",
             "fromPositionId": "pos-0044", "targetRequisitionId": "req-0015", "targetPositionId": "pos-0210",
             "type": "promotion", "status": "in_review", "requestedDate": "2026-07-10",
             "effectiveDate": None, "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-10T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

# ---- Learning & skills ----

register(_spec(
    name="skills_taxonomy",
    partition_key="/id",
    domain="learning",
    description="Canonical skills catalog with proficiency levels.",
    unique_keys=[["/skillId"]],
    seed="~80 skills across technical + functional + leadership, with category paths.",
    fields={
        "id": F("string"), "skillId": F("string"),
        "name": F("string"), "category": F("string"), "taxonomyPath": F("string"),
        "proficiencyLevels": F("array<string>", desc="e.g. ['novice','intermediate','advanced','expert']."),
        "type": F("string", desc="technical|functional|leadership|language"),
    },
    example={"id": "skill-product-strategy", "skillId": "skill-product-strategy",
             "name": "Product Strategy", "category": "Product", "taxonomyPath": "Product/Strategy",
             "proficiencyLevels": ["novice", "intermediate", "advanced", "expert"], "type": "functional",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="employee_skills",
    partition_key="/employeeId",
    domain="learning",
    description="An employee's assessed skills + levels (for skills-gap/intelligence skills).",
    unique_keys=[["/id"]],
    seed="~5-12 skills per employee.",
    fields={
        "id": F("string", desc="'es-<employeeId>-<skillId>'."),
        "employeeId": F("string", ref="employees.employeeId"),
        "skillId": F("string", ref="skills_taxonomy.skillId"),
        "currentLevel": F("string"), "targetLevel": F("string", required=False),
        "assessedDate": F("date"), "source": F("string", enum="skillSource"),
    },
    example={"id": "es-emp-0031-skill-python", "employeeId": "emp-0031", "skillId": "skill-python",
             "currentLevel": "advanced", "targetLevel": "expert", "assessedDate": "2026-06-01",
             "source": "manager_assessment", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-06-01T00:00:00Z", "updatedAt": "2026-06-01T00:00:00Z"},
))

register(_spec(
    name="learning_courses",
    partition_key="/id",
    domain="learning",
    description="Course catalog.",
    unique_keys=[["/courseId"]],
    seed="~30 courses incl. mandatory compliance training.",
    fields={
        "id": F("string"), "courseId": F("string"),
        "title": F("string"), "modality": F("string", enum="courseModality"),
        "durationHours": F("number"), "mandatory": F("bool"),
        "skillIdsCovered": F("array<string>", required=False, ref="skills_taxonomy.skillId"),
        "provider": F("string", required=False),
    },
    example={"id": "course-sec-101", "courseId": "course-sec-101", "title": "Security Awareness 101",
             "modality": "elearning", "durationHours": 1.0, "mandatory": True,
             "skillIdsCovered": ["skill-security-awareness"], "provider": "Internal", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z",
             "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="course_enrollments",
    partition_key="/employeeId",
    domain="learning",
    description="Employee course assignments/completions.",
    unique_keys=[["/enrollmentId"]],
    seed="Mandatory training enrollment for all; electives for some.",
    fields={
        "id": F("string"), "enrollmentId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "courseId": F("string", ref="learning_courses.courseId"),
        "assignedDate": F("date"), "completedDate": F("date", required=False),
        "score": F("number", required=False), "status": F("string", enum="enrollmentStatus"),
    },
    example={"id": "enr-1200", "enrollmentId": "enr-1200", "employeeId": "emp-0031",
             "courseId": "course-sec-101", "assignedDate": "2026-01-05", "completedDate": "2026-01-08",
             "score": 100, "status": "completed", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-05T00:00:00Z", "updatedAt": "2026-01-08T00:00:00Z"},
))

register(_spec(
    name="development_plans",
    partition_key="/employeeId",
    domain="learning",
    description="Individual development plans (IDPs).",
    unique_keys=[["/idpId"]],
    seed="IDP for ~30% of employees.",
    fields={
        "id": F("string"), "idpId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "managerId": F("string", ref="employees.employeeId"),
        "period": F("string"), "careerGoal": F("string", required=False),
        "activities": F("array<object>", desc="[{activity, targetSkillId, dueDate, status}]"),
        "status": F("string", desc="draft|active|completed"),
    },
    example={"id": "idp-0031", "idpId": "idp-0031", "employeeId": "emp-0031", "managerId": "emp-0006",
             "period": "2026", "careerGoal": "Move to Staff Engineer",
             "activities": [{"activity": "Lead a cross-team project", "targetSkillId": "skill-leadership",
                             "dueDate": "2026-12-31", "status": "in_progress"}],
             "status": "active", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-15T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

# ---- Workforce planning & analytics ----

register(_spec(
    name="workforce_plans",
    partition_key="/departmentId",
    domain="workforce",
    description="Headcount/capacity plans per department, with embedded forecasts + scenarios.",
    unique_keys=[["/planId"]],
    seed="One plan per major department for FY2026 with 2-3 scenarios each.",
    fields={
        "id": F("string"), "planId": F("string"),
        "departmentId": F("string", ref="departments.departmentId"),
        "fiscalYear": F("string"),
        "period": F("string", desc="== fiscalYear; partition alignment with analytics container."),
        "scenarioName": F("string", desc="base|upside|downside"),
        "currentHeadcount": F("int", derived=True), "plannedHeadcount": F("int"),
        "demandFte": F("number"), "supplyFte": F("number"), "gapFte": F("number", derived=True),
        "plannedHires": F("int"), "projectedAttrition": F("number"),
        "plannedCompCost": F("money"), "assumptions": F("string", required=False),
        "forecasts": F("array<object>", required=False,
                       desc="[{period, projectedHeadcount, projectedHires, projectedAttrition}]"),
    },
    example={"id": "wfp-eng-2026", "planId": "wfp-eng-2026", "departmentId": "dept-eng",
             "fiscalYear": "FY2026", "period": "FY2026", "scenarioName": "base", "currentHeadcount": 78,
             "plannedHeadcount": 92, "demandFte": 92, "supplyFte": 78, "gapFte": 14, "plannedHires": 18,
             "projectedAttrition": 4, "plannedCompCost": 14500000, "assumptions": "12% attrition",
             "forecasts": [{"period": "2026-Q4", "projectedHeadcount": 85, "projectedHires": 7,
                            "projectedAttrition": 2}],
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="org_snapshots",
    partition_key="/period",
    domain="workforce",
    description="Precomputed org/analytics snapshots (fixes cross-partition GROUP BY pain).",
    unique_keys=[["/snapshotId"]],
    seed="Monthly snapshots for the last 12 months, per department + a company roll-up.",
    fields={
        "id": F("string"), "snapshotId": F("string"),
        "period": F("string", desc="'YYYY-MM'; partition key for time-series scans."),
        "scope": F("string", desc="company|department."),
        "departmentId": F("string", required=False, ref="departments.departmentId"),
        "headcount": F("int"), "hires": F("int"), "terminations": F("int"),
        "attritionRate": F("number"), "avgSpanOfControl": F("number"), "layers": F("int"),
        "avgTenureYears": F("number"), "femalePercent": F("number", required=False),
        "avgCompaRatio": F("number"), "openReqs": F("int"),
    },
    example={"id": "snap-2026-07-eng", "snapshotId": "snap-2026-07-eng", "period": "2026-07",
             "scope": "department", "departmentId": "dept-eng", "headcount": 78, "hires": 3,
             "terminations": 1, "attritionRate": 0.013, "avgSpanOfControl": 6.4, "layers": 4,
             "avgTenureYears": 3.1, "femalePercent": 0.34, "avgCompaRatio": 0.97, "openReqs": 6,
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))


# ===========================================================================
# DOMAIN 5 — EMPLOYEE RELATIONS, COMPLIANCE & POLICY
# ===========================================================================

register(_spec(
    name="er_cases",
    partition_key="/employeeId",
    domain="employee_relations",
    description="Employee relations cases with embedded notes + investigation.",
    unique_keys=[["/caseId"]],
    seed="~20 cases across categories/severities; some with investigations.",
    fields={
        "id": F("string"), "caseId": F("string"),
        "employeeId": F("string", ref="employees.employeeId", desc="Subject/complainant."),
        "reportedById": F("string", required=False, ref="employees.employeeId"),
        "category": F("string", enum="caseCategory"), "severity": F("string", enum="caseSeverity"),
        "status": F("string", enum="caseStatus"),
        "assigneeId": F("string", ref="employees.employeeId", desc="HRBP/ER specialist."),
        "confidentialityLevel": F("string", desc="standard|restricted|highly_confidential"),
        "openedDate": F("date"), "closedDate": F("date", required=False),
        "summary": F("string"),
        "notes": F("array<object>", required=False, desc="[{authorId, timestamp, content, actionType}]"),
        "investigation": F("object", required=False,
                           desc="{leadInvestigatorId(ref employees), allegationType, findings, outcome}"),
    },
    exclude_paths=["/summary/?", "/notes/*", "/investigation/*"],
    example={"id": "case-0012", "caseId": "case-0012", "employeeId": "emp-0155", "reportedById": "emp-0033",
             "category": "policy_violation", "severity": "medium", "status": "investigating",
             "assigneeId": "emp-0009", "confidentialityLevel": "restricted", "openedDate": "2026-07-12",
             "closedDate": None, "summary": "Attendance policy concern.",
             "notes": [{"authorId": "emp-0009", "timestamp": "2026-07-13T10:00:00Z",
                        "content": "Initial intake completed.", "actionType": "intake"}],
             "investigation": None, "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-12T00:00:00Z", "updatedAt": "2026-07-14T00:00:00Z"},
))

register(_spec(
    name="disciplinary_actions",
    partition_key="/employeeId",
    domain="employee_relations",
    description="Formal disciplinary actions, optionally linked to a case.",
    unique_keys=[["/actionId"]],
    seed="~8 actions of varying severity.",
    fields={
        "id": F("string"), "actionId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "caseId": F("string", required=False, ref="er_cases.caseId"),
        "actionType": F("string", enum="disciplinaryType"),
        "issuedById": F("string", ref="employees.employeeId"),
        "effectiveDate": F("date"), "expirationDate": F("date", required=False),
        "reason": F("string"),
    },
    example={"id": "disc-0004", "actionId": "disc-0004", "employeeId": "emp-0155", "caseId": "case-0012",
             "actionType": "written_warning", "issuedById": "emp-0033", "effectiveDate": "2026-07-20",
             "expirationDate": "2027-07-20", "reason": "Repeated attendance issues.", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-07-20T00:00:00Z",
             "updatedAt": "2026-07-20T00:00:00Z"},
))

register(_spec(
    name="accommodation_requests",
    partition_key="/employeeId",
    domain="employee_relations",
    description="ADA/accessibility accommodation requests + interactive process.",
    unique_keys=[["/accommodationId"]],
    seed="~10 requests in mixed statuses.",
    fields={
        "id": F("string"), "accommodationId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "requestDate": F("date"), "conditionCategory": F("string", required=False),
        "requestedAccommodation": F("string"),
        "status": F("string", enum="accommodationStatus"),
        "handlerId": F("string", ref="employees.employeeId"),
        "approvedAccommodation": F("string", required=False),
        "interactiveProcessNotes": F("string", required=False), "reviewDate": F("date", required=False),
    },
    example={"id": "acc-0006", "accommodationId": "acc-0006", "employeeId": "emp-0077",
             "requestDate": "2026-06-01", "conditionCategory": "mobility",
             "requestedAccommodation": "Standing desk + ground-floor parking", "status": "implemented",
             "handlerId": "emp-0009", "approvedAccommodation": "Standing desk + reserved parking",
             "interactiveProcessNotes": "Completed with facilities.", "reviewDate": "2027-06-01",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-06-01T00:00:00Z", "updatedAt": "2026-06-20T00:00:00Z"},
))

register(_spec(
    name="policies",
    partition_key="/policyId",
    domain="compliance",
    description="THE single HR policy corpus (also synced to Azure Search). Numbers are canonical.",
    unique_keys=[["/policyId"]],
    seed="~25 policies; PTO numbers MUST match leave_policies (15/18/22).",
    fields={
        "id": F("string"), "policyId": F("string"),
        "title": F("string"), "category": F("string", enum="policyCategory"),
        "version": F("string"), "effectiveDate": F("date"), "jurisdiction": F("string"),
        "acknowledgmentRequired": F("bool"),
        "summary": F("string"), "content": F("string"),
        "sourceDocument": F("string", required=False), "embeddingId": F("string", required=False),
        "ownerId": F("string", required=False, ref="employees.employeeId"),
    },
    exclude_paths=["/content/?", "/summary/?"],
    example={"id": "policy-pto", "policyId": "policy-pto", "title": "Paid Time Off (PTO) Policy",
             "category": "leave", "version": "2026.1", "effectiveDate": "2026-01-01", "jurisdiction": "US",
             "acknowledgmentRequired": False,
             "summary": "Full-time employees accrue 15-22 PTO days/year based on tenure.",
             "content": "Full-time employees accrue PTO by tenure: 15 days (<2 yrs), 18 (2-5 yrs), 22 (5+).",
             "sourceDocument": "HR-Handbook-2026.pdf, p.14", "embeddingId": "emb-policy-pto",
             "ownerId": "emp-0009", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="policy_acknowledgments",
    partition_key="/employeeId",
    domain="compliance",
    description="Which employees acknowledged which policies.",
    unique_keys=[["/ackId"]],
    seed="Acks for policies where acknowledgmentRequired=true, most employees.",
    fields={
        "id": F("string"), "ackId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "policyId": F("string", ref="policies.policyId"),
        "acknowledgedDate": F("date"), "method": F("string", desc="portal|email|signature"),
    },
    example={"id": "ack-1500", "ackId": "ack-1500", "employeeId": "emp-0031", "policyId": "policy-conduct",
             "acknowledgedDate": "2026-01-10", "method": "portal", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-10T00:00:00Z",
             "updatedAt": "2026-01-10T00:00:00Z"},
))

register(_spec(
    name="compliance_requirements",
    partition_key="/id",
    domain="compliance",
    description="Regulatory obligations the company tracks (OSHA/EEO/FMLA/I-9/GDPR...).",
    unique_keys=[["/requirementId"]],
    seed="~15 requirements with owners + status.",
    fields={
        "id": F("string"), "requirementId": F("string"),
        "regulation": F("string", desc="OSHA|EEO|FMLA|I-9|GDPR|CCPA|ACA|..."),
        "description": F("string"), "jurisdiction": F("string"),
        "frequency": F("string", desc="annual|quarterly|per_event|ongoing"),
        "ownerId": F("string", ref="employees.employeeId"),
        "status": F("string", enum="complianceStatus"), "nextDueDate": F("date", required=False),
    },
    example={"id": "req-comp-i9", "requirementId": "req-comp-i9", "regulation": "I-9",
             "description": "Employment eligibility verification within 3 days of hire.",
             "jurisdiction": "US", "frequency": "per_event", "ownerId": "emp-0009",
             "status": "compliant", "nextDueDate": None, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z",
             "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="compliance_audits",
    partition_key="/id",
    domain="compliance",
    description="Audit records with findings + remediation.",
    unique_keys=[["/auditId"]],
    seed="~5 audits (I-9, pay equity, data privacy, safety, EEO).",
    fields={
        "id": F("string"), "auditId": F("string"),
        "type": F("string"), "scope": F("string"),
        "requirementId": F("string", required=False, ref="compliance_requirements.requirementId"),
        "startDate": F("date"), "completedDate": F("date", required=False),
        "leadId": F("string", ref="employees.employeeId"),
        "findings": F("array<object>", required=False, desc="[{finding, severity, remediation, status}]"),
        "overallStatus": F("string", enum="complianceStatus"),
    },
    example={"id": "audit-0002", "auditId": "audit-0002", "type": "pay_equity", "scope": "US, all depts",
             "requirementId": None, "startDate": "2026-05-01", "completedDate": "2026-06-01",
             "leadId": "emp-0009",
             "findings": [{"finding": "2% unexplained gap in Eng L4", "severity": "medium",
                           "remediation": "Adjust 3 salaries", "status": "in_progress"}],
             "overallStatus": "remediation", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-05-01T00:00:00Z", "updatedAt": "2026-06-01T00:00:00Z"},
))

register(_spec(
    name="background_checks",
    partition_key="/id",
    domain="compliance",
    description="Pre-hire/periodic background checks (candidate or employee).",
    unique_keys=[["/checkId"]],
    seed="One per recent hire (candidate-linked).",
    fields={
        "id": F("string"), "checkId": F("string"),
        "candidateId": F("string", required=False, ref="candidates.candidateId"),
        "employeeId": F("string", required=False, ref="employees.employeeId"),
        "vendorId": F("string", required=False, ref="vendors.vendorId"),
        "status": F("string", enum="backgroundCheckStatus"),
        "requestedDate": F("date"), "completedDate": F("date", required=False),
        "result": F("string", required=False),
    },
    example={"id": "bgc-0055", "checkId": "bgc-0055", "candidateId": "cand-0088", "employeeId": None,
             "vendorId": "vendor-checkr", "status": "clear", "requestedDate": "2026-08-06",
             "completedDate": "2026-08-10", "result": "No adverse findings.", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-08-06T00:00:00Z",
             "updatedAt": "2026-08-10T00:00:00Z"},
))

register(_spec(
    name="work_authorizations",
    partition_key="/employeeId",
    domain="compliance",
    description="Work authorization / visa records with embedded sponsorship tracking.",
    unique_keys=[["/authId"]],
    seed="Records for all; visa/sponsorship for the ~15% on visas.",
    fields={
        "id": F("string"), "authId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "status": F("string", enum="workAuthStatus"),
        "documentType": F("string", required=False, desc="passport|EAD|green_card|visa."),
        "country": F("string"), "expirationDate": F("date", required=False),
        "sponsorship": F("object", required=False,
                         desc="{visaCategory(H-1B/L-1/...), sponsorStatus, filingDate, "
                              "approvalDate, renewalDueDate}"),
    },
    example={"id": "auth-0006", "authId": "auth-0006", "employeeId": "emp-0006", "status": "citizen",
             "documentType": "passport", "country": "US", "expirationDate": None, "sponsorship": None,
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2020-06-01T00:00:00Z", "updatedAt": "2020-06-01T00:00:00Z"},
))

# ===========================================================================
# DOMAIN 6 — ENGAGEMENT & EXPERIENCE
# ===========================================================================

register(_spec(
    name="surveys",
    partition_key="/id",
    domain="engagement",
    description="Survey definitions (engagement/pulse/DEI/exit/...).",
    unique_keys=[["/surveyId"]],
    seed="~6 surveys incl. one recurring quarterly engagement pulse.",
    fields={
        "id": F("string"), "surveyId": F("string"),
        "name": F("string"), "type": F("string", enum="surveyType"),
        "launchDate": F("date"), "closeDate": F("date", required=False),
        "anonymous": F("bool"), "questionCount": F("int"),
        "participationRate": F("number", required=False, derived=True),
    },
    example={"id": "survey-2026-q2", "surveyId": "survey-2026-q2", "name": "Q2 2026 Engagement Pulse",
             "type": "engagement", "launchDate": "2026-04-15", "closeDate": "2026-04-30",
             "anonymous": True, "questionCount": 20, "participationRate": 0.82, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-04-01T00:00:00Z",
             "updatedAt": "2026-05-01T00:00:00Z"},
))

register(_spec(
    name="survey_responses",
    partition_key="/surveyId",
    domain="engagement",
    description="Responses (anonymized token when survey.anonymous).",
    unique_keys=[["/responseId"]],
    seed="Responses matching each survey's participation rate.",
    fields={
        "id": F("string"), "responseId": F("string"),
        "surveyId": F("string", ref="surveys.surveyId"),
        "employeeId": F("string", required=False, ref="employees.employeeId",
                       desc="null/token when anonymous."),
        "departmentId": F("string", required=False, ref="departments.departmentId"),
        "scores": F("array<object>", desc="[{questionId, score}]"),
        "comments": F("string", required=False), "submittedDate": F("date"),
        "engagementIndex": F("number", required=False, derived=True),
    },
    exclude_paths=["/comments/?"],
    example={"id": "resp-9001", "responseId": "resp-9001", "surveyId": "survey-2026-q2",
             "employeeId": None, "departmentId": "dept-eng",
             "scores": [{"questionId": "q1", "score": 4}], "comments": "Good direction.",
             "submittedDate": "2026-04-20", "engagementIndex": 7.9, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-04-20T00:00:00Z",
             "updatedAt": "2026-04-20T00:00:00Z"},
))

register(_spec(
    name="engagement_snapshots",
    partition_key="/departmentId",
    domain="engagement",
    description="Aggregated engagement/DEI metrics per department per period (precomputed).",
    unique_keys=[["/snapshotId"]],
    seed="Per department per survey period.",
    fields={
        "id": F("string"), "snapshotId": F("string"),
        "departmentId": F("string", ref="departments.departmentId"),
        "period": F("string"), "surveyId": F("string", required=False, ref="surveys.surveyId"),
        "engagementIndex": F("number"), "participationRate": F("number"),
        "enpsScore": F("number", required=False),
        "representation": F("object", required=False, desc="{genderPercents, ...} for DEI scorecards."),
    },
    example={"id": "eng-2026-q2-eng", "snapshotId": "eng-2026-q2-eng", "departmentId": "dept-eng",
             "period": "2026-Q2", "surveyId": "survey-2026-q2", "engagementIndex": 7.8,
             "participationRate": 0.85, "enpsScore": 32, "representation": {"female": 0.34, "male": 0.63},
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-05-01T00:00:00Z", "updatedAt": "2026-05-01T00:00:00Z"},
))

# ===========================================================================
# DOMAIN 7 — DOCUMENTS & ASSETS
# ===========================================================================

register(_spec(
    name="document_templates",
    partition_key="/id",
    domain="documents",
    description="Fillable document templates (I-9, NDA, offer, etc.).",
    unique_keys=[["/templateId"]],
    seed="~8 templates matching the workspace PDFs/DOCX.",
    fields={
        "id": F("string"), "templateId": F("string"),
        "name": F("string"), "type": F("string", enum="documentType"),
        "format": F("string", desc="pdf|docx"), "storageUrl": F("string"),
        "fields": F("array<string>", required=False, desc="Fillable field names."),
    },
    example={"id": "tmpl-i9", "templateId": "tmpl-i9", "name": "I-9 Employment Eligibility",
             "type": "i9", "format": "pdf", "storageUrl": "workspace://i9_form.pdf",
             "fields": ["employee_name", "employee_id", "start_date"], "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z",
             "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="documents",
    partition_key="/employeeId",
    domain="documents",
    description="Generated/stored documents tied to an employee.",
    unique_keys=[["/documentId"]],
    seed="Offer letters, I-9s, NDAs for recent hires; reviews for reviewed employees.",
    fields={
        "id": F("string"), "documentId": F("string"),
        "employeeId": F("string", required=False, ref="employees.employeeId"),
        "type": F("string", enum="documentType"),
        "templateId": F("string", required=False, ref="document_templates.templateId"),
        "status": F("string", desc="draft|generated|signed|verified|archived"),
        "generatedDate": F("date"), "signedDate": F("date", required=False),
        "verified": F("bool"), "blobUrl": F("string"),
    },
    example={"id": "doc-0050", "documentId": "doc-0050", "employeeId": "emp-0248", "type": "offer_letter",
             "templateId": "tmpl-offer", "status": "signed", "generatedDate": "2026-08-08",
             "signedDate": "2026-08-09", "verified": True,
             "blobUrl": "blob://generated-reports/doc-0050-offer-letter.pdf", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-08-08T00:00:00Z",
             "updatedAt": "2026-08-09T00:00:00Z"},
))

register(_spec(
    name="assets",
    partition_key="/employeeId",
    domain="documents",
    description="IT/physical assets, assigned to employees (null when in stock).",
    unique_keys=[["/assetId"]],
    seed="1-2 assets per active employee + a small in-stock pool (employeeId=null).",
    fields={
        "id": F("string"), "assetId": F("string"),
        "employeeId": F("string", required=False, ref="employees.employeeId"),
        "assetType": F("string", enum="assetType"), "model": F("string", required=False),
        "serialNumber": F("string", required=False), "status": F("string", enum="assetStatus"),
        "assignedDate": F("date", required=False), "returnedDate": F("date", required=False),
    },
    example={"id": "asset-0210", "assetId": "asset-0210", "employeeId": "emp-0031", "assetType": "laptop",
             "model": "MacBook Pro 14", "serialNumber": "C02X1234", "status": "assigned",
             "assignedDate": "2026-01-06", "returnedDate": None, "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-06T00:00:00Z",
             "updatedAt": "2026-01-06T00:00:00Z"},
))

# ===========================================================================
# DOMAIN 8 — HR SERVICE DELIVERY & VENDORS
# ===========================================================================

register(_spec(
    name="hr_tickets",
    partition_key="/employeeId",
    domain="service_delivery",
    description="HR help-desk tickets. employeeId is a REAL FK (fixes old 'emp-sam' orphans).",
    unique_keys=[["/ticketId"]],
    seed="~80 tickets across all categories; all employeeIds real; realistic SLA + statuses.",
    fields={
        "id": F("string"), "ticketId": F("string"),
        "employeeId": F("string", ref="employees.employeeId"),
        "employeeName": F("string", derived=True),
        "category": F("string", enum="ticketCategory"),
        "priority": F("string", enum="ticketPriority"),
        "status": F("string", enum="ticketStatus"),
        "subject": F("string"), "description": F("string"),
        "assigneeId": F("string", required=False, ref="employees.employeeId"),
        "policyReferenceId": F("string", required=False, ref="policies.policyId"),
        "openedDate": F("datetime"), "resolvedDate": F("datetime", required=False),
        "slaDueDate": F("datetime", required=False),
    },
    exclude_paths=["/description/?"],
    example={"id": "tkt-0123", "ticketId": "tkt-0123", "employeeId": "emp-0031", "employeeName": "Mia Brown",
             "category": "pto_leave", "priority": "medium", "status": "resolved",
             "subject": "How many PTO days do I have left?", "description": "Asking about 2026 balance.",
             "assigneeId": "emp-0009", "policyReferenceId": "policy-pto",
             "openedDate": "2026-07-18T10:00:00Z", "resolvedDate": "2026-07-18T15:00:00Z",
             "slaDueDate": "2026-07-21T10:00:00Z", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-18T10:00:00Z", "updatedAt": "2026-07-18T15:00:00Z"},
))

register(_spec(
    name="knowledge_articles",
    partition_key="/id",
    domain="service_delivery",
    description="Internal HR knowledge base articles (deflect tickets, feed chatbot).",
    unique_keys=[["/articleId"]],
    seed="~20 articles mapped to top ticket categories.",
    fields={
        "id": F("string"), "articleId": F("string"),
        "title": F("string"), "category": F("string", enum="ticketCategory"),
        "content": F("string"), "relatedPolicyId": F("string", required=False, ref="policies.policyId"),
        "views": F("int", required=False), "lastReviewedDate": F("date", required=False),
    },
    exclude_paths=["/content/?"],
    example={"id": "kb-0007", "articleId": "kb-0007", "title": "How PTO accrual works",
             "category": "pto_leave", "content": "You accrue PTO by tenure...",
             "relatedPolicyId": "policy-pto", "views": 412, "lastReviewedDate": "2026-06-01",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-06-01T00:00:00Z"},
))

register(_spec(
    name="vendors",
    partition_key="/id",
    domain="service_delivery",
    description="HR technology/service vendors.",
    unique_keys=[["/vendorId"]],
    seed="~12 vendors across categories.",
    fields={
        "id": F("string"), "vendorId": F("string"),
        "name": F("string"), "category": F("string", enum="vendorCategory"),
        "contractStart": F("date", required=False), "contractEnd": F("date", required=False),
        "annualCost": F("money", required=False), "ownerId": F("string", required=False, ref="employees.employeeId"),
        "status": F("string", desc="active|expired|evaluating"),
    },
    example={"id": "vendor-checkr", "vendorId": "vendor-checkr", "name": "Checkr", "category": "background_check",
             "contractStart": "2025-01-01", "contractEnd": "2026-12-31", "annualCost": 24000,
             "ownerId": "emp-0009", "status": "active", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2025-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
))


# ===========================================================================
# DOMAIN 9 — DATA GOVERNANCE & AI  (the explicitly called-out gap)
# These make the hr-ai-governance / hr-ai-privacy / hr-analytics-governance /
# hr-audit / data-quality skills actually runnable against real data.
# ===========================================================================

register(_spec(
    name="data_governance_policies",
    partition_key="/id",
    domain="governance",
    description="Governance policies (classification, retention, access, AI use).",
    unique_keys=[["/policyId"]],
    seed="~10 governance policies covering each dataClassification + AI usage.",
    fields={
        "id": F("string"), "policyId": F("string"),
        "title": F("string"),
        "domain": F("string", desc="classification|retention|access|ai_use|privacy|quality"),
        "appliesToClassifications": F("array<string>", enum="dataClassification"),
        "rule": F("string"), "ownerId": F("string", ref="employees.employeeId"),
        "effectiveDate": F("date"), "reviewDate": F("date", required=False),
    },
    example={"id": "dgp-pii-access", "policyId": "dgp-pii-access", "title": "PII Access Control Policy",
             "domain": "access", "appliesToClassifications": ["pii", "sensitive_pii"],
             "rule": "Access to PII requires role-based approval + logged purpose.", "ownerId": "emp-0009",
             "effectiveDate": "2026-01-01", "reviewDate": "2027-01-01", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z",
             "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="data_asset_catalog",
    partition_key="/id",
    domain="governance",
    description="Catalog of every HR data asset (container/field) with classification + owner.",
    unique_keys=[["/assetId"]],
    seed="One entry per container in THIS database + PII field maps for sensitive ones.",
    fields={
        "id": F("string"), "assetId": F("string"),
        "assetName": F("string", desc="Container name, e.g. 'employees'."),
        "dataDomain": F("string", desc="core_hr|payroll|benefits|talent|governance|..."),
        "classification": F("string", enum="dataClassification"),
        "containsPii": F("bool"),
        "piiFields": F("array<string>", required=False, desc="Field names holding PII."),
        "ownerId": F("string", ref="employees.employeeId"),
        "stewardId": F("string", required=False, ref="employees.employeeId"),
        "retentionScheduleId": F("string", required=False, ref="data_retention_schedules.scheduleId"),
        "systemOfRecord": F("string", desc="cosmos:closedai-hr"),
        "recordCount": F("int", required=False, derived=True),
        "qualityScore": F("number", required=False, derived=True, desc="0-1 from data_quality_issues."),
    },
    example={"id": "asset-employees", "assetId": "asset-employees", "assetName": "employees",
             "dataDomain": "core_hr", "classification": "sensitive_pii", "containsPii": True,
             "piiFields": ["dateOfBirth", "personalEmail", "phone", "compensation"], "ownerId": "emp-0009",
             "stewardId": "emp-0044", "retentionScheduleId": "ret-employee", "systemOfRecord": "cosmos:closedai-hr",
             "recordCount": 250, "qualityScore": 0.98, "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"},
))

register(_spec(
    name="data_access_logs",
    partition_key="/id",
    domain="governance",
    description="Audit trail: who accessed which sensitive HR data, when, why (for audits/DSAR).",
    unique_keys=[["/logId"]],
    seed="~300 access events across users/assets/purposes over the last 90 days.",
    fields={
        "id": F("string"), "logId": F("string"),
        "accessorId": F("string", ref="employees.employeeId"),
        "assetId": F("string", ref="data_asset_catalog.assetId"),
        "subjectEmployeeId": F("string", required=False, ref="employees.employeeId",
                              desc="Whose record was accessed."),
        "action": F("string", desc="read|export|update|delete"),
        "purpose": F("string"), "classification": F("string", enum="dataClassification"),
        "timestamp": F("datetime"), "approved": F("bool"), "sourceSystem": F("string", required=False),
    },
    example={"id": "acl-004201", "logId": "acl-004201", "accessorId": "emp-0009", "assetId": "asset-employees",
             "subjectEmployeeId": "emp-0031", "action": "read", "purpose": "payroll_processing",
             "classification": "sensitive_pii", "timestamp": "2026-08-18T14:22:00Z", "approved": True,
             "sourceSystem": "hr-agent", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-08-18T14:22:00Z", "updatedAt": "2026-08-18T14:22:00Z"},
))

register(_spec(
    name="ai_model_registry",
    partition_key="/id",
    domain="governance",
    description="Registry of AI systems used in HR, with risk tier + governance status (EU AI Act style).",
    unique_keys=[["/modelId"]],
    seed="~8 AI systems: resume screener, attrition predictor, chatbot, comp recommender, etc.",
    fields={
        "id": F("string"), "modelId": F("string"),
        "name": F("string"), "purpose": F("string"),
        "provider": F("string"), "modelType": F("string", desc="llm|classifier|regression|ranking|rules"),
        "riskTier": F("string", enum="aiRiskTier"),
        "status": F("string", enum="aiSystemStatus"),
        "ownerId": F("string", ref="employees.employeeId"),
        "usesPii": F("bool"), "trainingDataAssetIds": F("array<string>", required=False, ref="data_asset_catalog.assetId"),
        "lastBiasAuditDate": F("date", required=False), "biasAuditResult": F("string", required=False),
        "humanInLoop": F("bool"), "impactAssessmentId": F("string", required=False),
        "deployedDate": F("date", required=False),
    },
    example={"id": "ai-resume-screener", "modelId": "ai-resume-screener", "name": "Resume Screening Ranker",
             "purpose": "Rank inbound applications for recruiters.", "provider": "internal",
             "modelType": "ranking", "riskTier": "high", "status": "in_production", "ownerId": "emp-0044",
             "usesPii": True, "trainingDataAssetIds": ["asset-applications", "asset-candidates"],
             "lastBiasAuditDate": "2026-06-01", "biasAuditResult": "No adverse impact >4/5ths rule",
             "humanInLoop": True, "impactAssessmentId": "dpia-0002", "deployedDate": "2026-02-01",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-15T00:00:00Z",
             "updatedAt": "2026-06-01T00:00:00Z"},
))

register(_spec(
    name="ai_usage_logs",
    partition_key="/id",
    domain="governance",
    description="Usage/decision logs for registered AI systems (for AI governance + audit skills).",
    unique_keys=[["/usageId"]],
    seed="~200 usage events across AI systems over 90 days incl. some overridden decisions.",
    fields={
        "id": F("string"), "usageId": F("string"),
        "modelId": F("string", ref="ai_model_registry.modelId"),
        "userId": F("string", ref="employees.employeeId"),
        "subjectEmployeeId": F("string", required=False, ref="employees.employeeId"),
        "subjectCandidateId": F("string", required=False, ref="candidates.candidateId"),
        "decision": F("string", required=False), "confidence": F("number", required=False),
        "humanOverride": F("bool"), "overrideReason": F("string", required=False),
        "timestamp": F("datetime"),
    },
    example={"id": "aiu-010500", "usageId": "aiu-010500", "modelId": "ai-resume-screener", "userId": "emp-0044",
             "subjectEmployeeId": None, "subjectCandidateId": "cand-0088", "decision": "advance",
             "confidence": 0.87, "humanOverride": False, "overrideReason": None,
             "timestamp": "2026-07-10T09:00:00Z", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-07-10T09:00:00Z", "updatedAt": "2026-07-10T09:00:00Z"},
))

register(_spec(
    name="consent_records",
    partition_key="/employeeId",
    domain="governance",
    description="Employee/candidate consent by processing purpose (privacy skill).",
    unique_keys=[["/consentId"]],
    seed="Consent rows per employee per relevant purpose; a few withdrawn.",
    fields={
        "id": F("string"), "consentId": F("string"),
        "employeeId": F("string", required=False, ref="employees.employeeId"),
        "candidateId": F("string", required=False, ref="candidates.candidateId"),
        "purpose": F("string", enum="consentPurpose"),
        "status": F("string", enum="consentStatus"),
        "grantedDate": F("date", required=False), "withdrawnDate": F("date", required=False),
        "expiryDate": F("date", required=False), "legalBasis": F("string", required=False,
            desc="consent|contract|legal_obligation|legitimate_interest."),
    },
    example={"id": "consent-2201", "consentId": "consent-2201", "employeeId": "emp-0031", "candidateId": None,
             "purpose": "performance_analytics", "status": "granted", "grantedDate": "2026-01-01",
             "withdrawnDate": None, "expiryDate": None, "legalBasis": "legitimate_interest",
             "company": COMPANY, "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z",
             "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="dsar_requests",
    partition_key="/id",
    domain="governance",
    description="Data Subject Access Requests (GDPR/CCPA) with fulfillment tracking.",
    unique_keys=[["/dsarId"]],
    seed="~8 DSARs across types + statuses; some SLA-breaching.",
    fields={
        "id": F("string"), "dsarId": F("string"),
        "requesterEmployeeId": F("string", required=False, ref="employees.employeeId"),
        "requesterCandidateId": F("string", required=False, ref="candidates.candidateId"),
        "type": F("string", enum="dsarType"), "status": F("string", enum="dsarStatus"),
        "receivedDate": F("date"), "dueDate": F("date"), "completedDate": F("date", required=False),
        "assigneeId": F("string", ref="employees.employeeId"),
        "assetsInScope": F("array<string>", required=False, ref="data_asset_catalog.assetId"),
        "resolutionNotes": F("string", required=False),
    },
    example={"id": "dsar-0005", "dsarId": "dsar-0005", "requesterEmployeeId": "emp-0112",
             "requesterCandidateId": None, "type": "access", "status": "in_progress",
             "receivedDate": "2026-08-01", "dueDate": "2026-08-31", "completedDate": None,
             "assigneeId": "emp-0009", "assetsInScope": ["asset-employees", "asset-pay_statements"],
             "resolutionNotes": None, "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-10T00:00:00Z"},
))

register(_spec(
    name="data_retention_schedules",
    partition_key="/id",
    domain="governance",
    description="Retention rules per data asset/domain.",
    unique_keys=[["/scheduleId"]],
    seed="~10 schedules covering each domain (e.g. employee records 7y post-term).",
    fields={
        "id": F("string"), "scheduleId": F("string"),
        "dataDomain": F("string"), "retentionPeriodMonths": F("int"),
        "triggerEvent": F("string", desc="creation|termination|last_access|case_close."),
        "dispositionAction": F("string", desc="delete|anonymize|archive."),
        "legalHoldEligible": F("bool"), "ownerId": F("string", ref="employees.employeeId"),
    },
    example={"id": "ret-employee", "scheduleId": "ret-employee", "dataDomain": "core_hr",
             "retentionPeriodMonths": 84, "triggerEvent": "termination", "dispositionAction": "anonymize",
             "legalHoldEligible": True, "ownerId": "emp-0009", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z",
             "updatedAt": "2026-01-01T00:00:00Z"},
))

register(_spec(
    name="data_quality_issues",
    partition_key="/id",
    domain="governance",
    description="Tracked data-quality issues (drives quality scores + governance dashboards).",
    unique_keys=[["/issueId"]],
    seed="~30 issues across assets/rule types/severities; some resolved.",
    fields={
        "id": F("string"), "issueId": F("string"),
        "assetId": F("string", ref="data_asset_catalog.assetId"),
        "ruleType": F("string", desc="completeness|validity|uniqueness|consistency|referential_integrity|timeliness."),
        "field": F("string", required=False), "affectedRecordCount": F("int"),
        "severity": F("string", enum="dqSeverity"), "status": F("string", enum="dqStatus"),
        "detectedDate": F("date"), "resolvedDate": F("date", required=False),
        "ownerId": F("string", ref="employees.employeeId"), "description": F("string"),
    },
    example={"id": "dqi-0021", "issueId": "dqi-0021", "assetId": "asset-employees",
             "ruleType": "completeness", "field": "personalEmail", "affectedRecordCount": 12,
             "severity": "low", "status": "open", "detectedDate": "2026-08-15", "resolvedDate": None,
             "ownerId": "emp-0044", "description": "12 employees missing personalEmail.", "company": COMPANY,
             "schemaVersion": SCHEMA_VERSION, "createdAt": "2026-08-15T00:00:00Z",
             "updatedAt": "2026-08-15T00:00:00Z"},
))

register(_spec(
    name="integrations",
    partition_key="/id",
    domain="governance",
    description="System integrations/data flows (HRIS<->payroll<->ATS) for lineage + audits.",
    unique_keys=[["/integrationId"]],
    seed="~8 integrations linking vendors + assets with health status.",
    fields={
        "id": F("string"), "integrationId": F("string"),
        "name": F("string"), "sourceSystem": F("string"), "targetSystem": F("string"),
        "vendorId": F("string", required=False, ref="vendors.vendorId"),
        "dataAssetIds": F("array<string>", required=False, ref="data_asset_catalog.assetId"),
        "direction": F("string", desc="inbound|outbound|bidirectional"),
        "frequency": F("string", desc="realtime|hourly|daily|weekly"),
        "status": F("string", enum="integrationStatus"),
        "lastSyncAt": F("datetime", required=False), "ownerId": F("string", ref="employees.employeeId"),
    },
    example={"id": "intg-hris-payroll", "integrationId": "intg-hris-payroll", "name": "HRIS to Payroll Sync",
             "sourceSystem": "cosmos:closedai-hr", "targetSystem": "payroll-vendor", "vendorId": "vendor-adp",
             "dataAssetIds": ["asset-employees", "asset-compensation_records"], "direction": "outbound",
             "frequency": "daily", "status": "active", "lastSyncAt": "2026-08-18T02:00:00Z",
             "ownerId": "emp-0009", "company": COMPANY, "schemaVersion": SCHEMA_VERSION,
             "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-08-18T02:00:00Z"},
))


# ===========================================================================
# REFERENTIAL INTEGRITY, COVERAGE & POPULATION ORDER
# ===========================================================================

# Hard invariants the populator MUST satisfy and the validator MUST check.
# (FK invariants are auto-derived from field `ref`s via foreign_keys(); these are
# the extra structural/semantic rules that go beyond simple FK existence.)
REFERENTIAL_RULES: list[str] = [
    "employees: exactly ONE doc has managerId == null (the CEO, jobLevel 8). Everyone else's "
    "managerId resolves to a real employee.",
    "employees: the managerId graph is a single tree (no cycles), depth <= 5 layers.",
    "employees: for every non-CEO, manager.jobLevel > employee.jobLevel (managers outrank reports).",
    "employees.isPeopleManager / directReportCount are recomputed from who reports to whom.",
    "employees.compensation.annualSalary lies within its band (compensation_bands by jobFamily+level); "
    "compaRatio = salary / band.mid.",
    "departments: exactly ONE root (parentDepartmentId == null, levelType == 'company'); "
    "no cycles; layerLevel = depth from root.",
    "departments.headcount / openHeadcount are recomputed from employees + positions.",
    "positions: status=='filled' <=> incumbentEmployeeId is set AND that employee.positionId == this position "
    "(1:1). status=='open' => incumbentEmployeeId null and (usually) a requisitionId set.",
    "Every active employee has exactly one filled position; open positions map to open requisitions.",
    "PTO is consistent end-to-end: leave_policies.accrualTiers -> leave_balances.accruedDays -> "
    "employees.ptoSnapshot; usedDays = sum(approved/taken pto leave_requests for the year); "
    "policies('policy-pto').content text MUST state the same 15/18/22 numbers.",
    "benefits: employees.benefitsSnapshot is derived from the employee's ACTIVE benefits_elections doc; "
    "plan ids/names match benefits_plans.",
    "payroll: payroll_runs totals == sum of their pay_statements; pay_statements.employeeId active in that period.",
    "recruiting funnel: application.stage=='hired' => an offer exists with status=='accepted' AND "
    "application.hiredEmployeeId points to a real, recently-created employee whose hireDate == offer.startDate.",
    "hr_tickets / onboarding_checklists / offboarding_checklists: EVERY employeeId resolves (no orphans "
    "like the old 'emp-sam').",
    "policy_acknowledgments only reference policies where acknowledgmentRequired == true.",
    "data_asset_catalog has one row PER container in this database; recordCount matches seeded volume; "
    "qualityScore reflects open data_quality_issues for that asset.",
    "ai_model_registry: any riskTier=='high' system in production has humanInLoop==true and a "
    "lastBiasAuditDate within 12 months.",
    "All derived (derived=True) fields are COMPUTED, never hand-authored, and stay consistent with their source.",
    "No snake_case field names; every FK is an id that resolves; no ''/'N/A' placeholders (use null).",
]

# Minimum breadth so the DB 'feels complete' and skills reliably find data.
COVERAGE_TARGETS: dict[str, str] = {
    "employees": "~250, one connected tree, every department populated, mix of levels/tenures/locations.",
    "departments": "1 company root + 8-10 departments (+ a few teams).",
    "leave_requests": "Year-round history for most employees so PTO math is real.",
    "pay_statements": "Latest 1-2 runs for all active employees.",
    "benefits_elections": "One active election per active employee.",
    "performance_reviews": "One per active employee for the last closed cycle.",
    "hr_tickets": "~80 across ALL ticketCategory values (esp. payroll, benefits, data_privacy).",
    "er_cases": "~20 across categories/severities.",
    "policies": "~25 covering every policyCategory.",
    "data_asset_catalog": "One row per container (~50).",
    "data_access_logs": "~300 events; ai_usage_logs ~200; enough for audit/governance skills.",
    "ai_model_registry": "~8 systems spanning risk tiers incl. >=1 'high' in production.",
    "dsar_requests": "~8 across dsarType + statuses.",
    "org_snapshots": "12 monthly snapshots per department + company roll-up.",
}

# Dependency tiers: populate strictly top-to-bottom so every FK target exists first.
POPULATION_ORDER: list[list[str]] = [
    # Tier 0 — no FKs (catalogs)
    ["job_families", "locations", "skills_taxonomy", "leave_policies", "benefits_plans",
     "pay_groups", "document_templates", "vendors", "data_retention_schedules",
     "review_cycles", "surveys", "learning_courses", "compliance_requirements"],
    # Tier 1 — depend on Tier 0
    ["jobs", "compensation_bands", "data_governance_policies"],
    # Tier 2 — org spine (self-referential trees resolved within the tier)
    ["departments", "employees"],
    # Tier 3 — depend on employees/departments/jobs
    ["positions", "policies", "job_requisitions", "candidates", "ai_model_registry",
     "data_asset_catalog"],
    # Tier 4 — operational + lifecycle
    ["applications", "compensation_records", "payroll_runs", "benefits_elections",
     "leave_requests", "timesheets", "goals", "employee_skills", "course_enrollments",
     "development_plans", "recognition_awards", "policy_acknowledgments",
     "work_authorizations", "assets", "consent_records", "workforce_plans",
     "accommodation_requests", "hr_tickets", "knowledge_articles", "integrations"],
    # Tier 5 — depend on Tier 4
    ["interviews", "offers", "pay_statements", "leave_balances", "bonus_payouts",
     "equity_grants", "performance_reviews", "feedback", "succession_plans",
     "internal_mobility", "background_checks", "survey_responses", "documents",
     "er_cases", "compliance_audits", "dsar_requests", "ai_usage_logs",
     "data_access_logs", "data_quality_issues"],
    # Tier 6 — depend on Tier 5 (created after employees exist)
    ["onboarding_checklists", "offboarding_checklists", "exit_interviews",
     "disciplinary_actions", "pips"],
    # Tier 7 — precomputed analytics (compute last from everything above)
    ["org_snapshots", "engagement_snapshots"],
]


def population_order() -> list[str]:
    """Flat list of container names in dependency-safe population order."""
    return [name for tier in POPULATION_ORDER for name in tier]


def foreign_keys() -> list[dict[str, str]]:
    """Auto-derived FK graph across all containers.

    Returns [{container, field, targetContainer, targetField}, ...].
    Single source of truth shared by the populator and validator.
    """
    out: list[dict[str, str]] = []
    for c in CONTAINERS:
        for local, target in c.foreign_keys():
            tc, _, tf = target.partition(".")
            out.append({
                "container": c.name,
                "field": local,
                "targetContainer": tc,
                "targetField": tf,
            })
    return out


# ===========================================================================
# PHYSICAL LAYOUT  (Cosmos-idiomatic consolidation)
# ---------------------------------------------------------------------------
# The 70 specs above are LOGICAL ENTITIES. On a provisioned Cosmos account a
# shared-throughput database caps at 25 containers, and one-container-per-entity
# is a relational anti-pattern anyway. So entities are consolidated into a few
# PHYSICAL containers, grouped by partition key / access pattern. Every document
# carries `recordType` (== its entity name) to disambiguate within a container.
#
# Populator contract:
#   * Write each entity's docs into its mapped physical container.
#   * Stamp `recordType` = entity name on every doc.
#   * Ensure the physical container's partition-key field is populated on the doc
#     (e.g. everything in `employee_records` must carry `employeeId`).
# ===========================================================================

# Alias: the registered specs are logical entities.
ENTITIES = CONTAINERS


@dataclass
class PhysicalContainer:
    name: str
    partition_key: str        # e.g. "/employeeId" — MUST exist on every member entity
    description: str
    entities: list[str]
    composite_indexes: list[list[dict]] = dc_field(default_factory=list)


PHYSICAL_CONTAINERS: list[PhysicalContainer] = [
    PhysicalContainer(
        name="employees",
        partition_key="/employeeId",
        description="Employee system-of-record spine. Kept alone for fast point reads and "
                    "org/headcount queries.",
        entities=["employees"],
        composite_indexes=[[{"path": "/departmentId", "order": "ascending"},
                            {"path": "/employmentStatus", "order": "ascending"}]],
    ),
    PhysicalContainer(
        name="employee_records",
        partition_key="/employeeId",
        description="All per-employee operational documents, co-located by employeeId so one "
                    "person's entire record is a single-partition read.",
        entities=[
            "pay_statements", "compensation_records", "bonus_payouts", "equity_grants",
            "benefits_elections", "leave_requests", "leave_balances", "timesheets",
            "performance_reviews", "goals", "feedback", "pips", "recognition_awards",
            "employee_skills", "course_enrollments", "development_plans",
            "policy_acknowledgments", "work_authorizations", "assets", "documents",
            "consent_records", "er_cases", "disciplinary_actions", "accommodation_requests",
            "internal_mobility", "onboarding_checklists", "offboarding_checklists",
            "exit_interviews", "hr_tickets",
        ],
    ),
    PhysicalContainer(
        name="org",
        partition_key="/id",
        description="Org structure + job architecture catalogs (departments, locations, jobs, "
                    "bands, positions, succession).",
        entities=["departments", "locations", "job_families", "jobs", "compensation_bands",
                  "positions", "succession_plans"],
    ),
    PhysicalContainer(
        name="reference",
        partition_key="/recordType",
        description="Global reference/config data, read-mostly, partitioned by recordType.",
        entities=["policies", "leave_policies", "benefits_plans", "pay_groups",
                  "skills_taxonomy", "learning_courses", "document_templates", "vendors",
                  "review_cycles", "surveys", "compliance_requirements",
                  "data_governance_policies", "data_retention_schedules", "knowledge_articles",
                  "ai_model_registry", "data_asset_catalog"],
    ),
    PhysicalContainer(
        name="recruiting",
        partition_key="/requisitionId",
        description="ATS funnel co-located by requisition (reqs, applications, interviews, offers).",
        entities=["job_requisitions", "applications", "interviews", "offers"],
    ),
    PhysicalContainer(
        name="candidates",
        partition_key="/id",
        description="Candidate/talent pool records (queried by candidate).",
        entities=["candidates"],
    ),
    PhysicalContainer(
        name="operations",
        partition_key="/recordType",
        description="Org-wide operational records (payroll runs, audits, background checks, "
                    "DSARs, integrations).",
        entities=["payroll_runs", "compliance_audits", "background_checks", "dsar_requests",
                  "integrations"],
    ),
    PhysicalContainer(
        name="governance_logs",
        partition_key="/recordType",
        description="High-volume audit/telemetry (data-access logs, AI usage logs, data-quality "
                    "issues) for governance + audit skills.",
        entities=["data_access_logs", "ai_usage_logs", "data_quality_issues"],
    ),
    PhysicalContainer(
        name="analytics",
        partition_key="/period",
        description="Precomputed time-series analytics (org + engagement snapshots, workforce "
                    "plans) — sidesteps cross-partition GROUP BY.",
        entities=["org_snapshots", "engagement_snapshots", "workforce_plans"],
    ),
    PhysicalContainer(
        name="survey_responses",
        partition_key="/surveyId",
        description="Survey responses co-located by survey.",
        entities=["survey_responses"],
    ),
]


def entity_to_container() -> dict[str, str]:
    """entity name -> physical container name."""
    out: dict[str, str] = {}
    for pc in PHYSICAL_CONTAINERS:
        for e in pc.entities:
            out[e] = pc.name
    return out


def entity_spec(name: str) -> ContainerSpec:
    for c in CONTAINERS:
        if c.name == name:
            return c
    raise KeyError(name)


def _physical_exclude_paths(pc: PhysicalContainer) -> list[str]:
    """Union of member entities' big-text exclude paths."""
    paths: list[str] = []
    for e in pc.entities:
        for p in entity_spec(e).exclude_paths:
            if p not in paths:
                paths.append(p)
    return paths


# ===========================================================================
# SERIALIZATION HELPERS (spec as data — for the populator / validator / docs)
# ===========================================================================

def spec_as_dict(c: ContainerSpec) -> dict:
    mapping = entity_to_container()
    example = dict(c.example)
    example.setdefault("recordType", c.name)  # docs are stamped with their entity name
    return {
        "entity": c.name,
        "recordType": c.name,
        "physicalContainer": mapping.get(c.name),
        "logicalPartitionKey": c.partition_key,
        "domain": c.domain,
        "description": c.description,
        "uniqueKeys": c.unique_keys,
        "excludePaths": c.exclude_paths,
        "compositeIndexes": c.composite_indexes,
        "seed": c.seed,
        "foreignKeys": [{"field": f, "target": t} for f, t in c.foreign_keys()],
        "fields": c.fields,
        "example": example,
    }


def physical_layout() -> list[dict]:
    return [{
        "name": pc.name,
        "partitionKey": pc.partition_key,
        "description": pc.description,
        "entities": pc.entities,
        "excludePaths": _physical_exclude_paths(pc),
        "compositeIndexes": pc.composite_indexes,
    } for pc in PHYSICAL_CONTAINERS]


def full_spec() -> dict:
    return {
        "database": DATABASE_NAME,
        "company": COMPANY,
        "schemaVersion": SCHEMA_VERSION,
        "physicalContainerCount": len(PHYSICAL_CONTAINERS),
        "entityCount": len(CONTAINERS),
        "physicalContainers": physical_layout(),
        "entityToContainer": entity_to_container(),
        "enums": ENUMS,
        "populationOrder": population_order(),
        "referentialRules": REFERENTIAL_RULES,
        "coverageTargets": COVERAGE_TARGETS,
        "foreignKeys": foreign_keys(),
        "entities": [spec_as_dict(c) for c in CONTAINERS],
    }


def _sanity_check() -> list[str]:
    """Validate the SCHEMA itself (not data): unique names, resolvable FK targets,
    every container present in POPULATION_ORDER exactly once."""
    problems: list[str] = []
    names = [c.name for c in CONTAINERS]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        problems.append(f"Duplicate container names: {sorted(dupes)}")

    valid_targets = {f"{c.name}.{fname}" for c in CONTAINERS for fname in c.fields}
    for c in CONTAINERS:
        for local, target in c.foreign_keys():
            if target not in valid_targets:
                problems.append(f"{c.name}.{local} -> unresolved FK target '{target}'")

    ordered = population_order()
    missing = set(names) - set(ordered)
    extra = set(ordered) - set(names)
    if missing:
        problems.append(f"Containers missing from POPULATION_ORDER: {sorted(missing)}")
    if extra:
        problems.append(f"POPULATION_ORDER names not defined as containers: {sorted(extra)}")
    dup_order = {n for n in ordered if ordered.count(n) > 1}
    if dup_order:
        problems.append(f"Containers listed twice in POPULATION_ORDER: {sorted(dup_order)}")

    # ---- physical layout validation ----
    mapped: list[str] = [e for pc in PHYSICAL_CONTAINERS for e in pc.entities]
    mapped_set = set(mapped)
    entity_names = set(names)
    unmapped = entity_names - mapped_set
    if unmapped:
        problems.append(f"Entities not assigned to a physical container: {sorted(unmapped)}")
    ghost = mapped_set - entity_names
    if ghost:
        problems.append(f"Physical containers reference unknown entities: {sorted(ghost)}")
    dup_mapped = {e for e in mapped if mapped.count(e) > 1}
    if dup_mapped:
        problems.append(f"Entities mapped to >1 physical container: {sorted(dup_mapped)}")
    pc_names = [pc.name for pc in PHYSICAL_CONTAINERS]
    if len(pc_names) != len(set(pc_names)):
        problems.append("Duplicate physical container names.")
    if len(pc_names) > 25:
        problems.append(f"{len(pc_names)} physical containers exceeds shared-throughput cap of 25.")
    # partition-key field must exist on every member entity (recordType is meta-guaranteed)
    for pc in PHYSICAL_CONTAINERS:
        pk_field = pc.partition_key.lstrip("/")
        for e in pc.entities:
            spec = entity_spec(e)
            if pk_field not in spec.fields:
                problems.append(
                    f"{pc.name}: entity '{e}' lacks partition-key field '{pk_field}'.")
    return problems


# ===========================================================================
# PROVISIONING  (creates the NEW database + all containers, idempotently)
# ===========================================================================

def _build_indexing_policy(exclude_paths: list[str], composite: list[list[dict]]) -> dict:
    policy: dict[str, Any] = {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": '/"_etag"/?'}] + [{"path": p} for p in exclude_paths],
    }
    if composite:
        policy["compositeIndexes"] = composite
    return policy


def _load_env() -> None:
    """Best-effort load of the repo-root .env so COSMOS_* vars are available
    when this script is run directly from a shell."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    here = os.path.dirname(os.path.abspath(__file__))
    # repo root is two levels up (HRAgent_Main/scripts/ -> repo root)
    for candidate in (
        os.path.join(here, "..", "..", ".env"),
        os.path.join(here, "..", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ):
        if os.path.exists(candidate):
            load_dotenv(candidate, override=False)
            return


def account_is_serverless() -> bool | None:
    """Return True/False if the account capability can be read, else None.

    Serverless accounts must NOT be given throughput; provisioned accounts need
    it (and cap shared-throughput databases at 25 containers)."""
    _load_env()
    uri = os.getenv("COSMOS_URI") or os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    if not uri or not key:
        return None
    try:
        from azure.cosmos import CosmosClient  # type: ignore
        client = CosmosClient(uri, credential=key)
        # A serverless database cannot report/replace throughput; provisioned can.
        # Cheapest reliable probe: create a throwaway db, ask for its offer.
        probe = "closedai-serverless-probe"
        db = client.create_database_if_not_exists(id=probe)
        serverless = False
        try:
            db.read_offer()  # raises on serverless (no offer resource)
        except Exception as e:  # noqa: BLE001
            if "serverless" in str(e).lower() or "NotFound" in type(e).__name__:
                serverless = True
        client.delete_database(probe)
        return serverless
    except Exception:  # noqa: BLE001
        return None


def provision(throughput: int = 1000, recreate: bool = False) -> None:
    """Create DATABASE_NAME with database-level shared autoscale throughput and all
    PHYSICAL containers. Idempotent by default.

    throughput      : autoscale MAX RU/s shared across the database (matches the
                      existing closedai-db cost model; autoscale floors at 10%).
    recreate        : if True, delete the database first (DESTRUCTIVE — dev only).

    Note: Cosmos already guarantees `id` uniqueness per logical partition, so no
    custom unique-key policy is set (and `/id` is rejected as a system property).
    """
    _load_env()
    try:
        from azure.cosmos import CosmosClient, PartitionKey, exceptions  # type: ignore
        from azure.cosmos import ThroughputProperties  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit("azure-cosmos not installed. `pip install azure-cosmos`.") from e

    problems = _sanity_check()
    if problems:
        raise SystemExit("Refusing to provision — schema is inconsistent:\n  - "
                         + "\n  - ".join(problems))

    uri = os.getenv("COSMOS_URI") or os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    if not uri or not key:
        raise SystemExit("Set COSMOS_URI and COSMOS_KEY in the environment (.env).")

    client = CosmosClient(uri, credential=key)

    if recreate:
        try:
            client.delete_database(DATABASE_NAME)
            print(f"Deleted existing database '{DATABASE_NAME}'.")
        except exceptions.CosmosResourceNotFoundError:
            pass

    db = client.create_database_if_not_exists(
        id=DATABASE_NAME,
        offer_throughput=ThroughputProperties(auto_scale_max_throughput=throughput),
    )
    print(f"Database ready: '{DATABASE_NAME}' "
          f"(shared autoscale max {throughput} RU/s, {len(PHYSICAL_CONTAINERS)} containers, "
          f"{len(CONTAINERS)} entity types)")

    created, existing = 0, 0
    for pc in PHYSICAL_CONTAINERS:
        kwargs: dict[str, Any] = {
            "id": pc.name,
            "partition_key": PartitionKey(path=pc.partition_key),
            "indexing_policy": _build_indexing_policy(
                _physical_exclude_paths(pc), pc.composite_indexes),
        }
        try:
            db.create_container(**kwargs)
            created += 1
            print(f"  + created {pc.name:<18} pk {pc.partition_key:<16} "
                  f"({len(pc.entities)} entity type(s))")
        except exceptions.CosmosResourceExistsError:
            existing += 1
            print(f"  = exists  {pc.name}")
    print(f"Done. {created} created, {existing} already existed.")


# ===========================================================================
# MARKDOWN EXPORT  (human-readable data dictionary generated from the specs)
# ===========================================================================

def to_markdown() -> str:
    mapping = entity_to_container()
    lines = [f"# {DATABASE_NAME} — Data Dictionary",
             "",
             f"Company: **{COMPANY}** · Schema version: **{SCHEMA_VERSION}** · "
             f"Physical containers: **{len(PHYSICAL_CONTAINERS)}** · "
             f"Entity types: **{len(CONTAINERS)}**",
             "",
             "> Generated from `hr_database_schema.py`. This is the target-state spec the "
             "populator must conform to.",
             "",
             "## Physical containers",
             "",
             "| container | partition key | entity types |",
             "|---|---|---|"]
    for pc in PHYSICAL_CONTAINERS:
        lines.append(f"| `{pc.name}` | `{pc.partition_key}` | {', '.join(pc.entities)} |")
    lines.append("")
    by_domain: dict[str, list[ContainerSpec]] = {}
    for c in CONTAINERS:
        by_domain.setdefault(c.domain, []).append(c)
    for domain, specs in by_domain.items():
        lines.append(f"## Domain: {domain}")
        lines.append("")
        for c in specs:
            lines.append(f"### `{c.name}`  (recordType `{c.name}` in container "
                         f"`{mapping.get(c.name)}`)")
            lines.append("")
            lines.append(c.description)
            lines.append("")
            if c.seed:
                lines.append(f"*Seed target:* {c.seed}")
                lines.append("")
            lines.append("| field | type | req | enum | ref | derived | notes |")
            lines.append("|---|---|---|---|---|---|---|")
            for fname, spec in c.fields.items():
                lines.append(
                    f"| `{fname}` | {spec['type']} | {'Y' if spec['required'] else ''} | "
                    f"{spec['enum'] or ''} | {spec['ref'] or ''} | "
                    f"{'Y' if spec['derived'] else ''} | {spec['desc']} |"
                )
            lines.append("")
    return "\n".join(lines)


# ===========================================================================
# CLI
# ===========================================================================

def _main() -> None:
    parser = argparse.ArgumentParser(description="ClosedAI HR greenfield DB schema & provisioning.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prov = sub.add_parser("provision", help="Create the new database + all containers.")
    p_prov.add_argument("--throughput", type=int, default=1000,
                        help="Shared autoscale MAX RU/s at DB level (default 1000).")
    p_prov.add_argument("--recreate", action="store_true",
                        help="DESTRUCTIVE: delete the database first (dev only).")

    sub.add_parser("print-spec", help="Print the full machine-readable spec as JSON.")
    sub.add_parser("layout", help="Print the physical container layout as JSON.")
    sub.add_parser("fk-graph", help="Print the auto-derived foreign-key graph as JSON.")
    sub.add_parser("order", help="Print the dependency-safe population order.")
    sub.add_parser("markdown", help="Print the human-readable data dictionary (markdown).")
    sub.add_parser("check", help="Validate the schema definitions themselves.")
    sub.add_parser("probe", help="Report whether the Cosmos account is serverless.")

    args = parser.parse_args()

    if args.cmd == "provision":
        provision(throughput=args.throughput, recreate=args.recreate)
    elif args.cmd == "print-spec":
        print(json.dumps(full_spec(), indent=2))
    elif args.cmd == "layout":
        print(json.dumps(physical_layout(), indent=2))
    elif args.cmd == "fk-graph":
        print(json.dumps(foreign_keys(), indent=2))
    elif args.cmd == "order":
        print(json.dumps(population_order(), indent=2))
    elif args.cmd == "markdown":
        print(to_markdown())
    elif args.cmd == "probe":
        result = account_is_serverless()
        if result is None:
            print("Could not determine account type (missing creds or SDK error).")
        else:
            print(f"serverless: {result}  "
                  f"({'no throughput needed' if result else 'provisioned — throughput required'})")
    elif args.cmd == "check":
        problems = _sanity_check()
        if problems:
            print(f"SCHEMA PROBLEMS ({len(problems)}):")
            for p in problems:
                print("  - " + p)
            raise SystemExit(1)
        print(f"OK — {len(PHYSICAL_CONTAINERS)} physical containers, {len(CONTAINERS)} entity types, "
              f"{len(foreign_keys())} FK edges, schema is self-consistent.")


if __name__ == "__main__":
    _main()
