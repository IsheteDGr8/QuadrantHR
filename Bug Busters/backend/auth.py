from fastapi import Depends, HTTPException, Request

from logger import get_logger

logger = get_logger(__name__)

# Real Entra ID / MSAL sign-in has been removed from this project (was
# JWT validation against Microsoft's JWKS endpoint - see git history for
# ENTRA_TENANT_ID/ENTRA_CLIENT_ID and PyJWKClient if that ever comes back).
# The only login path now is the demo fallback (demo_login_db.py /
# POST /demo-login), which returns a role with no token, session, or
# signature of any kind.
#
# So this is NOT authentication - it trusts whatever the caller puts in
# these headers, no verification at all. Anyone can set X-Demo-Role: HR
# and get HR access. That's an accepted tradeoff for a demo/hackathon
# project with no real user data at stake - do not reuse this approach
# anywhere real auth matters.
ROLE_HEADER = "X-Demo-Role"
EMAIL_HEADER = "X-Demo-Email"
NAME_HEADER = "X-Demo-Name"


class CurrentUser:
    def __init__(self, *, object_id: str, roles: list[str], name: str | None = None):
        self.object_id = object_id
        self.roles = roles
        self.name = name or object_id

    def has_role(self, role: str) -> bool:
        return role in self.roles


def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency: reads identity/role straight from headers the
    frontend sets after a demo login. No verification - see module
    docstring. Raises 401 only if the headers are missing entirely.
    """
    email = request.headers.get(EMAIL_HEADER, "").strip()
    role = request.headers.get(ROLE_HEADER, "").strip()

    if not email or not role:
        raise HTTPException(
            status_code=401,
            detail=f"Missing {EMAIL_HEADER}/{ROLE_HEADER} headers. Sign in via /demo-login first.",
        )

    name = request.headers.get(NAME_HEADER, "").strip() or None

    return CurrentUser(object_id=email, roles=[role], name=name)


def require_role(*allowed_roles: str):
    """Dependency factory: Depends(require_role("HR", "Manager")) blocks
    the request with 403 unless the caller's X-Demo-Role header is one of
    the listed roles. Composes with get_current_user rather than
    duplicating its logic.
    """

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(user.has_role(role) for role in allowed_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}.",
            )

        return user

    return dependency
