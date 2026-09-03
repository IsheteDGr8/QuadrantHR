"""Pytest configuration, explicit test auth, and database cleanup fixtures."""

from __future__ import annotations

import pytest
from fastapi import Header, HTTPException, status
from sqlalchemy import func, or_

from database.connection import SessionLocal
from database.models_db import DepartmentUserDB, TicketDB
from services.jwt_verifier import parse_jwt_claims_unverified, verify_azure_user


def _verified_test_user(authorization: str | None = Header(default=None)) -> dict:
    """Resolve explicit test JWT claims without weakening production auth.

    Endpoint tests intentionally use locally-created, unsigned JWT-shaped values.
    FastAPI's dependency override mechanism is the correct trust boundary for
    those tests; the production verifier continues to require a valid signature.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required.",
        )
    token = authorization[7:].strip()
    try:
        _, claims = parse_jwt_claims_unverified(token)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid test JWT structure.",
        ) from error

    oid = claims.get("oid") or claims.get("sub")
    email = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
    if not oid or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Test JWT requires oid and email claims.",
        )

    role = claims.get("role") or "Employee"
    department = claims.get("department")
    with SessionLocal() as session:
        record = (
            session.query(DepartmentUserDB)
            .filter(
                or_(
                    DepartmentUserDB.azure_object_id == oid,
                    func.lower(DepartmentUserDB.user_email) == email.lower(),
                )
            )
            .first()
        )
        if record:
            role = record.role or role
            department = record.department_name or department

    return {
        "oid": oid,
        "email": email,
        "name": claims.get("name") or email,
        "role": role,
        "department": department,
        "claims": claims,
    }


@pytest.fixture(scope="session", autouse=True)
def explicit_http_test_auth():
    """Install test-only auth overrides on both supported app import paths."""
    from backend.main import app as package_app
    from main import app as flat_app

    apps = {id(app): app for app in (package_app, flat_app)}.values()
    for app in apps:
        app.dependency_overrides[verify_azure_user] = _verified_test_user
    yield
    for app in apps:
        app.dependency_overrides.pop(verify_azure_user, None)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_created_tickets():
    """Record pre-test ticket IDs and remove any new tickets created during test execution."""
    with SessionLocal() as db:
        initial_ids = {t.id for t in db.query(TicketDB.id).all()}

    yield

    with SessionLocal() as db:
        if initial_ids:
            new_tickets = db.query(TicketDB).filter(~TicketDB.id.in_(initial_ids)).all()
        else:
            new_tickets = db.query(TicketDB).all()
        for t in new_tickets:
            db.delete(t)
        db.commit()
