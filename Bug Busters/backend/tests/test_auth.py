import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user, require_role, CurrentUser, ROLE_HEADER, EMAIL_HEADER, NAME_HEADER


def _build_test_app():
    app = FastAPI()

    @app.get("/whoami")
    def whoami(user: CurrentUser = Depends(get_current_user)):
        return {"object_id": user.object_id, "name": user.name, "roles": user.roles}

    @app.get("/hr-only")
    def hr_only(user: CurrentUser = Depends(require_role("HR"))):
        return {"name": user.name}

    return app


client = TestClient(_build_test_app())


# --------------------------------------------------
# get_current_user
# --------------------------------------------------

def test_valid_headers_return_identity():
    response = client.get(
        "/whoami",
        headers={EMAIL_HEADER: "manager@bugbusters.demo", ROLE_HEADER: "Manager"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "object_id": "manager@bugbusters.demo",
        "name": "manager@bugbusters.demo",
        "roles": ["Manager"],
    }


def test_name_header_used_when_present():
    response = client.get(
        "/whoami",
        headers={
            EMAIL_HEADER: "manager@bugbusters.demo",
            ROLE_HEADER: "Manager",
            NAME_HEADER: "Demo Manager User",
        },
    )

    assert response.json()["name"] == "Demo Manager User"


def test_missing_headers_returns_401():
    response = client.get("/whoami")

    assert response.status_code == 401


def test_missing_role_header_returns_401():
    response = client.get("/whoami", headers={EMAIL_HEADER: "hr@bugbusters.demo"})

    assert response.status_code == 401


def test_missing_email_header_returns_401():
    response = client.get("/whoami", headers={ROLE_HEADER: "HR"})

    assert response.status_code == 401


def test_blank_headers_return_401():
    response = client.get("/whoami", headers={EMAIL_HEADER: "   ", ROLE_HEADER: "   "})

    assert response.status_code == 401


# --------------------------------------------------
# require_role
# --------------------------------------------------

def test_require_role_allows_matching_role():
    response = client.get(
        "/hr-only",
        headers={EMAIL_HEADER: "hr@bugbusters.demo", ROLE_HEADER: "HR"},
    )

    assert response.status_code == 200


def test_require_role_blocks_non_matching_role():
    response = client.get(
        "/hr-only",
        headers={EMAIL_HEADER: "intern@bugbusters.demo", ROLE_HEADER: "Intern"},
    )

    assert response.status_code == 403


def test_require_role_blocks_missing_headers():
    response = client.get("/hr-only")

    assert response.status_code == 401
