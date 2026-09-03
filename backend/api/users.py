"""User Profiles API Router for TicketGenie."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database.crud import get_user_profile, update_user_profile
from services.jwt_verifier import verify_azure_user

router = APIRouter(prefix="/users", tags=["users"])


class UserProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None


class AzureLoginRequest(BaseModel):
    azure_object_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    id_token: Optional[str] = None


@router.get("/profile")
def handle_get_profile(
    user_id: Optional[str] = None,
    current_user: dict = Depends(verify_azure_user),
):
    user_oid = current_user.get("oid")
    user_email = current_user.get("email")
    role = (current_user.get("role") or "").lower()
    can_select_user = "admin" in role or "manager" in role
    scoped_user_id = user_id if can_select_user else None

    profile = get_user_profile(
        user_id=scoped_user_id, azure_oid=user_oid, email=user_email
    )
    if not profile:
        profile = update_user_profile(
            user_id=f"usr-admin-{user_oid[:8]}",
            name=current_user.get("name")
            or (user_email.split("@")[0] if user_email else user_oid),
            email=user_email,
            department=current_user.get("department") or "General",
        )
    return profile


@router.put("/profile")
def handle_update_profile(
    req: UserProfileUpdateRequest,
    user_id: Optional[str] = None,
    current_user: dict = Depends(verify_azure_user),
):
    user_oid = current_user.get("oid")
    role = (current_user.get("role") or "").lower()
    can_select_user = "admin" in role or "manager" in role
    target_user_id = (
        user_id if user_id and can_select_user else f"usr-admin-{user_oid[:8]}"
    )
    return update_user_profile(
        user_id=target_user_id,
        name=req.name,
        email=req.email or current_user.get("email"),
        phone=req.phone,
        department=req.department,
    )


@router.get("/upper-management")
def get_upper_management_users(
    current_user: dict = Depends(verify_azure_user),
):
    from sqlalchemy import func

    from database.connection import SessionLocal
    from database.models_db import DepartmentUserDB, UserProfileDB

    users = []
    seen_names = set()

    with SessionLocal() as session:
        dept_users = (
            session.query(DepartmentUserDB)
            .filter(func.lower(DepartmentUserDB.department_name).contains("upper"))
            .all()
        )
        for du in dept_users:
            profile = None
            if du.azure_object_id:
                profile = (
                    session.query(UserProfileDB)
                    .filter(
                        func.lower(UserProfileDB.azure_object_id)
                        == du.azure_object_id.lower()
                    )
                    .first()
                )
            if not profile and du.user_email:
                profile = (
                    session.query(UserProfileDB)
                    .filter(func.lower(UserProfileDB.email) == du.user_email.lower())
                    .first()
                )

            name = (
                profile.name
                if profile
                and profile.name
                and profile.name not in ["Admin1", "Employee1", "Azure User", "User"]
                else (
                    du.user_email.split("@")[0]
                    if du.user_email
                    else "Upper Management Admin"
                )
            )
            role = du.role or (profile.role if profile else "Admin")
            email = du.user_email or (profile.email if profile else None)

            if name not in seen_names:
                seen_names.add(name)
                users.append(
                    {
                        "id": du.id,
                        "name": name,
                        "email": email,
                        "role": role,
                        "department": du.department_name,
                    }
                )

        profiles = (
            session.query(UserProfileDB)
            .filter(
                func.lower(UserProfileDB.department).contains("upper"),
                func.lower(UserProfileDB.role) != "employee",
            )
            .all()
        )
        for p in profiles:
            if p.name and p.name not in seen_names:
                seen_names.add(p.name)
                users.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "email": p.email,
                        "role": p.role,
                        "department": p.department,
                    }
                )

    defaults = [
        {
            "name": "Greg Davis",
            "role": "Admin & VP Operations",
            "department": "Upper Executive Management",
        },
        {
            "name": "Sarah Jenkins",
            "role": "Director of HR & Operations",
            "department": "Upper Management",
        },
        {
            "name": "Alex Vance",
            "role": "Chief Operations Officer",
            "department": "Upper Management",
        },
    ]
    for d in defaults:
        existing = next((u for u in users if u["name"] == d["name"]), None)
        if existing:
            if existing.get("role") in ["Employee", "Member", None]:
                existing["role"] = d["role"]
        elif d["name"] not in seen_names:
            seen_names.add(d["name"])
            users.append(d)

    return users


@router.post("/azure-login")
def handle_azure_login(req: AzureLoginRequest):
    from services.jwt_verifier import verify_azure_jwt

    jwt_verified = False
    verified_oid = req.azure_object_id
    claims = {}

    if req.id_token:
        try:
            claims = verify_azure_jwt(req.id_token)
            jwt_verified = True
            print("DEBUG Claims received from Microsoft token:", claims)
            token_oid = claims.get("oid") or claims.get("sub")
            if token_oid:
                verified_oid = token_oid
            print(
                f"✅ [Azure Auth API] Microsoft JWT signature verified for OID: {verified_oid}"
            )
        except Exception as err:
            print(f"⚠️ [Azure Auth API] JWT verification warning: {err}")

    from sqlalchemy import func

    from database.connection import SessionLocal
    from database.models_db import DepartmentUserDB

    is_admin = False
    role = "Employee"
    department = "General Staff"

    with SessionLocal() as session:
        record = (
            session.query(DepartmentUserDB)
            .filter(DepartmentUserDB.azure_object_id == verified_oid)
            .first()
        )
        if not record and req.email:
            record = (
                session.query(DepartmentUserDB)
                .filter(func.lower(DepartmentUserDB.user_email) == req.email.lower())
                .first()
            )
            if record:
                record.azure_object_id = verified_oid
                session.commit()
        if record:
            if "admin" in record.role.lower():
                is_admin = True
            if record.role:
                role = record.role
            if record.department_name:
                department = record.department_name
            # Automatically update user_email on mapping if missing
            if req.email and not record.user_email:
                record.user_email = req.email
                session.commit()

    PLACEHOLDER_NAMES = {"Admin1", "Employee1", "Azure User", "User", ""}

    # Resolution order:
    # 1. req.name from frontend (MSAL fetches this from Graph API — most accurate)
    # 2. JWT given_name + family_name claims
    # 3. JWT name claim (raw Azure AD display name — may be a placeholder)
    # 4. Email prefix as last resort
    displayName = None

    if req.name and req.name.strip() not in PLACEHOLDER_NAMES:
        displayName = req.name.strip()

    if not displayName and claims:
        given_name = claims.get("given_name", "").strip()
        family_name = claims.get("family_name", "").strip()
        if given_name and family_name:
            displayName = f"{given_name} {family_name}"
        else:
            jwt_name = (claims.get("name") or "").strip()
            if jwt_name and jwt_name not in PLACEHOLDER_NAMES:
                displayName = jwt_name

    if not displayName:
        displayName = req.email.split("@")[0] if req.email else "Azure User"

    # If a manually-set real name already exists in the DB, keep it
    profile_id = f"usr-admin-{verified_oid[:8]}"
    with SessionLocal() as session:
        from database.models_db import UserProfileDB

        db_profile = (
            session.query(UserProfileDB)
            .filter(func.lower(UserProfileDB.azure_object_id) == verified_oid.lower())
            .first()
        )
        if not db_profile and req.email:
            db_profile = (
                session.query(UserProfileDB)
                .filter(func.lower(UserProfileDB.email) == req.email.lower())
                .first()
            )
        if not db_profile:
            db_profile = (
                session.query(UserProfileDB)
                .filter(UserProfileDB.id == profile_id)
                .first()
            )
        if db_profile:
            profile_id = db_profile.id
            if (
                db_profile.name
                and db_profile.name.strip() not in PLACEHOLDER_NAMES
                and displayName in PLACEHOLDER_NAMES
            ):
                displayName = db_profile.name

    # Synchronize user_profiles table from JWT claims upon login
    if req.email or displayName:
        try:
            from database.crud import update_user_profile

            update_user_profile(
                user_id=profile_id,
                name=displayName,
                email=req.email,
                role=role,
                department=department,
                azure_object_id=verified_oid,
            )
        except Exception as err:
            print(f"Notice: profile sync during login: {err}")

    print(
        f"👤 [Azure Auth API] User {verified_oid} authenticated as role: '{role}', is_admin: {is_admin}, jwt_verified: {jwt_verified}"
    )
    return {
        "status": "success",
        "azure_object_id": verified_oid,
        "is_admin": is_admin,
        "role": role,
        "department": department,
        "jwt_verified": jwt_verified,
        "email": req.email,
        "name": displayName,
    }
