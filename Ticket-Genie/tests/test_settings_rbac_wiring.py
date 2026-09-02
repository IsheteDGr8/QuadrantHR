"""Regression coverage for the Super Admin RBAC assignment form."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.admin import DepartmentCreateRequest, handle_create_department
from database.connection import SessionLocal
from database.crud import list_departments
from database.models_db import DepartmentDB

SETTINGS_VIEW = Path("frontend/src/views/SettingsView.svelte")


def test_rbac_assignment_uses_real_azure_object_id():
    source = SETTINGS_VIEW.read_text(encoding="utf-8")

    assert "rbacAssignObjectId" in source
    assert 'placeholder="Azure Object ID (GUID)"' in source
    assert "azure_object_id: azureObjectId" in source
    assert "rbacAssignEmail" not in source
    assert "uobj-${Date.now()" not in source
    assert "user_email: rbacAssign" not in source


def test_department_ui_only_reports_success_after_api_confirmation():
    source = SETTINGS_VIEW.read_text(encoding="utf-8")
    handler = source.split("async function handleAddDepartment()", 1)[1].split(
        "async function handleRemoveDepartment", 1
    )[0]

    assert "await apiCreateDepartment(departmentName, queueName)" in handler
    assert "await loadAdminData()" in handler
    assert "newDeptName = ''" in handler
    assert "departments = [...departments" not in handler
    assert "created!`" not in handler.split("catch (e)", 1)[1]


def test_super_admin_department_creation_persists_and_is_idempotent():
    department_name = f"Verification Department {uuid4().hex[:8]}"
    request = DepartmentCreateRequest(
        name=department_name,
        queue_name="Verification Queue",
        description="Temporary automated verification record",
    )

    try:
        created = handle_create_department(
            request,
            current_user={"oid": "test-super-admin", "role": "Super Admin"},
        )
        repeated = handle_create_department(
            request,
            current_user={"oid": "test-super-admin", "role": "Super Admin"},
        )

        assert created["name"] == department_name
        assert created["queue_name"] == "Verification Queue"
        assert repeated["id"] == created["id"]
        assert any(
            department["id"] == created["id"] for department in list_departments()
        )
    finally:
        with SessionLocal() as db:
            db.query(DepartmentDB).filter(DepartmentDB.name == department_name).delete()
            db.commit()


def test_non_super_admin_cannot_create_department():
    request = DepartmentCreateRequest(name="Forbidden Department", queue_name="None")

    with pytest.raises(HTTPException) as error:
        handle_create_department(
            request,
            current_user={"oid": "test-employee", "role": "Employee"},
        )

    assert error.value.status_code == 403
