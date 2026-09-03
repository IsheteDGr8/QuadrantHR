"""Microsoft Entra ID JWT Signature & Claims Verification Module for TicketGenie."""

import base64
import json
import logging
import os
import time
import urllib.request
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, status

logger = logging.getLogger("ticketgenie.jwt_verifier")

# In-memory JWKS cache
_JWKS_CACHE: Dict[str, Any] = {"keys": {}, "expires_at": 0}
JWKS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"


def fetch_microsoft_jwks() -> Dict[str, Any]:
    """Fetch and cache Microsoft Entra ID OIDC public keys (JWKS)."""
    now = time.time()
    if _JWKS_CACHE["expires_at"] > now and _JWKS_CACHE["keys"]:
        return _JWKS_CACHE["keys"]

    try:
        req = urllib.request.Request(
            JWKS_URL, headers={"User-Agent": "TicketGenie-Backend"}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                _JWKS_CACHE["keys"] = {key["kid"]: key for key in data.get("keys", [])}
                _JWKS_CACHE["expires_at"] = now + 86400  # Cache for 24 hours
                logger.info("Successfully refreshed Microsoft Entra ID JWKS keys.")
                return _JWKS_CACHE["keys"]
    except Exception as e:
        logger.warning(f"Failed to fetch Microsoft JWKS keys: {e}")
        _JWKS_CACHE["expires_at"] = (
            now + 60
        )  # Cache failure for 1 min to prevent stalling all subsequent requests
    return _JWKS_CACHE.get("keys", {})


def base64url_decode(input_str: str) -> bytes:
    """Decode base64url-encoded string."""
    rem = len(input_str) % 4
    if rem > 0:
        input_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(input_str)


def parse_jwt_claims_unverified(token: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse JWT header and payload without signature validation."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format.")
    header = json.loads(base64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(base64url_decode(parts[1]).decode("utf-8"))
    return header, payload


def verify_azure_jwt(token: str) -> Dict[str, Any]:
    """
    Verifies Microsoft Entra ID JWT token:
    1. Checks JWT structure & expiration (exp).
    2. Validates audience (AZURE_CLIENT_ID) if configured.
    3. Validates RSA signature via PyJWT if available.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization token.",
        )

    # Clean Bearer prefix if present
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    try:
        header, payload = parse_jwt_claims_unverified(token)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT token structure.",
        ) from err

    # 1. Check expiration
    now = time.time()
    exp = payload.get("exp")
    if exp and now > exp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )

    azure_client_id = os.getenv("AZURE_CLIENT_ID", "").strip()

    # 2. Check audience if AZURE_CLIENT_ID is configured
    aud = payload.get("aud")
    if azure_client_id and aud and aud != azure_client_id:
        logger.warning(
            f"JWT audience mismatch: expected '{azure_client_id}', got '{aud}'"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token audience mismatch.",
        )

    # 3. Signature verification is mandatory. Claims from an unverified token
    # are never accepted as identity.
    try:
        import jwt as pyjwt
        from jwt.algorithms import RSAAlgorithm

        jwks = fetch_microsoft_jwks()
        kid = header.get("kid")
        if kid and kid in jwks:
            public_key = RSAAlgorithm.from_jwk(json.dumps(jwks[kid]))
            verified_payload = pyjwt.decode(
                token,
                key=public_key,
                algorithms=["RS256"],
                options={"verify_aud": bool(azure_client_id)},
                audience=azure_client_id if azure_client_id else None,
            )
            logger.info("Successfully verified Microsoft JWT RSA signature via JWKS.")
            return verified_payload
    except ImportError as exc:
        logger.error("JWT cryptography dependency is unavailable.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature could not be verified.",
        ) from exc
    except Exception as exc:
        logger.warning("JWT signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature.",
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token signing key is unavailable.",
    )


def verify_azure_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    FastAPI Security Dependency:
    Extracts and verifies Bearer token from 'Authorization' header.
    Returns authenticated user claims (oid, email, name, role).
    Strictly raises 401 Unauthorized if Authorization header is missing in production.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required.",
        )

    claims = verify_azure_jwt(authorization)
    oid = claims.get("oid") or claims.get("sub") or claims.get("homeAccountId")
    if not oid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT claims: missing object ID (oid).",
        )

    email = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT claims: missing email identity.",
        )

    given_name = claims.get("given_name")
    family_name = claims.get("family_name")
    if given_name and family_name:
        name = f"{given_name} {family_name}".strip()
    else:
        name = claims.get("name") or email

    role = claims.get("role") or (
        claims.get("roles")[0]
        if isinstance(claims.get("roles"), list) and claims.get("roles")
        else "Employee"
    )
    department = claims.get("department") or claims.get("dept")
    try:
        from sqlalchemy import func, or_

        from database.connection import SessionLocal
        from database.models_db import DepartmentUserDB

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
                if record.role:
                    role = record.role
                if record.department_name:
                    department = record.department_name

            from database.models_db import UserProfileDB

            profile_id = f"usr-admin-{oid[:8]}"
            db_profile = (
                session.query(UserProfileDB)
                .filter(UserProfileDB.id == profile_id)
                .first()
            )
            if db_profile and db_profile.name:
                if name in [
                    "Admin1",
                    "Employee1",
                    "Azure User",
                    "User",
                ] or db_profile.name not in [
                    "Admin1",
                    "Employee1",
                    "Azure User",
                    "User",
                ]:
                    name = db_profile.name
    except Exception as err:
        logger.warning(f"Database role/department lookup notice: {err}")

    return {
        "oid": oid,
        "email": email,
        "name": name,
        "role": role,
        "department": department,
        "claims": claims,
    }
