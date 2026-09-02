"""One-time (or whenever-you-update-the-list) script: uploads the curated
reference links into the Azure AI Search index.

Run manually, not part of the app's runtime:

    AZURE_SEARCH_ADMIN_KEY=<admin-key> python seed_reference_links.py

Needs the search service's admin key (not the runtime query key) — run
search_index_setup.py first if the index doesn't exist yet.

policy_type values must match backend/main.py's PolicyType enum exactly,
or get_reference_links()'s filter won't match anything at query time.
"""

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from settings import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX

REFERENCE_LINKS = [
    {
        "id": "hipaa-security-rule",
        "policy_type": "Security Policy",
        "title": "HIPAA Security Rule",
        "url": "https://www.hhs.gov/hipaa/for-professionals/security/index.html",
        "source": "U.S. Department of Health & Human Services",
        "description": "Federal standards for protecting electronic personal health information.",
    },
    {
        "id": "fmla-leave-act",
        "policy_type": "Leave Policy",
        "title": "Family and Medical Leave Act (FMLA)",
        "url": "https://www.dol.gov/agencies/whd/fmla",
        "source": "U.S. Department of Labor",
        "description": "Federal law guaranteeing eligible employees unpaid, job-protected leave for qualifying family and medical reasons.",
    },
    {
        "id": "flsa-overtime",
        "policy_type": "Attendance Policy",
        "title": "Fair Labor Standards Act (FLSA) — Overtime Pay",
        "url": "https://www.dol.gov/agencies/whd/overtime",
        "source": "U.S. Department of Labor",
        "description": "Federal rules governing minimum wage and overtime pay eligibility for hourly and salaried workers.",
    },
    {
        "id": "eeoc-conduct",
        "policy_type": "Code of Conduct",
        "title": "Equal Employment Opportunity Laws",
        "url": "https://www.eeoc.gov/statutes/statutes",
        "source": "U.S. Equal Employment Opportunity Commission",
        "description": "Federal laws prohibiting workplace discrimination and harassment on the basis of protected characteristics.",
    },
    {
        "id": "irs-mileage-rates-expense",
        "policy_type": "Expense Reimbursement",
        "title": "IRS Standard Mileage Rates",
        "url": "https://www.irs.gov/tax-professionals/standard-mileage-rates",
        "source": "Internal Revenue Service",
        "description": "Annual standard mileage rates for calculating the deductible or reimbursable cost of business vehicle use.",
    },
    {
        "id": "irs-mileage-rates-travel",
        "policy_type": "Travel Policy",
        "title": "IRS Standard Mileage Rates",
        "url": "https://www.irs.gov/tax-professionals/standard-mileage-rates",
        "source": "Internal Revenue Service",
        "description": "Annual standard mileage rates for calculating the deductible or reimbursable cost of business vehicle use.",
    },
]


def main() -> None:
    admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")

    if not (AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_INDEX and admin_key):
        raise SystemExit(
            "Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_INDEX (via .env or "
            "the environment) and AZURE_SEARCH_ADMIN_KEY before running this "
            "script."
        )

    client = SearchClient(
        AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, AzureKeyCredential(admin_key)
    )

    results = client.upload_documents(documents=REFERENCE_LINKS)

    for result in results:
        status = "OK" if result.succeeded else f"FAILED — {result.error_message}"
        print(f"{result.key}: {status}")


if __name__ == "__main__":
    main()
