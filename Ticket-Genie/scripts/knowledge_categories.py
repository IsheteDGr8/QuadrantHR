"""
Deterministic filename -> access-category mapping for the synthetic
Northstar Technologies knowledge base in the `ticket-genie-knowledge`
Blob container.

This is a plain, human-reviewable lookup table - NOT a GPT decision. It
exists because the blobs in the container are flat (no per-category
folders) and currently carry no metadata, so something has to assign each
document's `category` before it can be indexed and role-filtered.

Categories must exactly match backend/services/role_service.py's scope
names: General, HR, IT, Accounting, WorkplaceOperations, UpperManagement.

If new files are added to the container, add them here explicitly -
scripts using this map fail loudly on any unmapped blob rather than
guessing.
"""

CATEGORY_GENERAL = "General"
CATEGORY_HR = "HR"
CATEGORY_IT = "IT"
CATEGORY_ACCOUNTING = "Accounting"
CATEGORY_WORKPLACE_OPERATIONS = "WorkplaceOperations"
CATEGORY_UPPER_MANAGEMENT = "UpperManagement"

ALL_CATEGORIES = {
    CATEGORY_GENERAL,
    CATEGORY_HR,
    CATEGORY_IT,
    CATEGORY_ACCOUNTING,
    CATEGORY_WORKPLACE_OPERATIONS,
    CATEGORY_UPPER_MANAGEMENT,
}

BLOB_CATEGORY_MAP = {
    "approved_software_catalog.xlsx": CATEGORY_IT,
    "badge_building_access_sop.docx": CATEGORY_WORKPLACE_OPERATIONS,
    "company_card_procedures.pdf": CATEGORY_ACCOUNTING,
    "cross_department_incident_playbook.pdf": CATEGORY_UPPER_MANAGEMENT,
    "employee_handbook.pdf": CATEGORY_GENERAL,
    "executive_escalation_matrix.pdf": CATEGORY_UPPER_MANAGEMENT,
    "expense_reimbursement_manual.pdf": CATEGORY_ACCOUNTING,
    "facilities_request_matrix.xlsx": CATEGORY_WORKPLACE_OPERATIONS,
    "hr_leave_management_handbook.pdf": CATEGORY_HR,
    "hr_offboarding_checklist.docx": CATEGORY_HR,
    "hr_onboarding_sop.docx": CATEGORY_HR,
    "identity_access_sop.docx": CATEGORY_IT,
    "it_support_playbook.pdf": CATEGORY_IT,
    "manager_hr_escalation_guide.pdf": CATEGORY_HR,
    "reimbursement_review_sop.docx": CATEGORY_ACCOUNTING,
    "service_catalog.csv": CATEGORY_GENERAL,
    "standard_request_field_guide.docx": CATEGORY_GENERAL,
    "technical_troubleshooting_guide.pdf": CATEGORY_IT,
    "ticket_genie_employee_portal_guide.pdf": CATEGORY_GENERAL,
    "workplace_faq.docx": CATEGORY_WORKPLACE_OPERATIONS,
    "workplace_operations_manual.pdf": CATEGORY_WORKPLACE_OPERATIONS,
}


def category_for_blob(blob_name: str) -> str:
    """Look up the deterministic category for a blob, or raise if unmapped."""

    try:
        return BLOB_CATEGORY_MAP[blob_name]
    except KeyError as exc:
        raise KeyError(
            f"No category mapping for blob '{blob_name}'. Add it to "
            "scripts/knowledge_categories.py before indexing - do not guess."
        ) from exc
