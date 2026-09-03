import asyncio
import io
from unittest.mock import patch

import pytest
from fastapi import HTTPException, UploadFile

from services import knowledge_ingestion_service as ingestion


@pytest.mark.parametrize("role", ["Admin", "Super Admin", "Ticketer", " admin "])
def test_only_canonical_management_roles_are_allowed(role):
    user = {"role": role, "oid": "oid-1"}
    assert ingestion.require_knowledge_manager(user) is user


@pytest.mark.parametrize("role", ["Employee", "Manager", "Support", "", None])
def test_employee_and_legacy_roles_cannot_manage_knowledge(role):
    with pytest.raises(HTTPException) as exc:
        ingestion.require_knowledge_manager({"role": role, "oid": "oid-1"})
    assert exc.value.status_code == 403


def test_chunker_preserves_all_policy_text():
    text = "Eligibility rules.\n\n" + ("Coverage details. " * 400) + "\n\nAppeals."
    chunks = ingestion._chunks(text, target_chars=500, overlap_chars=50)
    assert len(chunks) > 2
    assert chunks[0].startswith("Eligibility rules")
    assert chunks[-1].endswith("Appeals.")


def test_service_principal_is_valid_blob_identity_configuration():
    with patch.dict(
        "os.environ",
        {
            "AZURE_TENANT_ID": "tenant",
            "AZURE_CLIENT_ID": "client",
            "AZURE_CLIENT_SECRET": "secret",
        },
        clear=True,
    ):
        assert ingestion._has_azure_identity_configuration() is True


def test_partial_service_principal_configuration_fails_closed():
    with patch.dict(
        "os.environ",
        {"AZURE_TENANT_ID": "tenant", "AZURE_CLIENT_ID": "client"},
        clear=True,
    ):
        assert ingestion._has_azure_identity_configuration() is False


def test_rejects_unsupported_upload_before_cloud_access():
    upload = UploadFile(filename="policy.exe", file=io.BytesIO(b"not a policy"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ingestion.ingest_document(
                upload,
                title="Bad policy",
                category="General",
                uploaded_by={"oid": "oid-1", "email": "admin@example.com"},
            )
        )
    assert exc.value.status_code == 415


def test_enterprise_seed_pack_covers_core_employee_policy_domains():
    from pathlib import Path

    seed_dir = Path(__file__).parents[1] / "knowledge_seed"
    names = {path.name for path in seed_dir.glob("*.md")}
    assert {
        "employee_benefits_and_insurance.md",
        "paid_time_off_and_vacation.md",
        "sick_safe_and_family_leave.md",
        "retirement_and_financial_wellness.md",
        "equal_employment_anti_discrimination.md",
        "workplace_accommodations.md",
    } <= names
