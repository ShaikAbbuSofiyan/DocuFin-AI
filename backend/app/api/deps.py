from typing import Any, Callable, Dict, List, Optional
from fastapi import Cookie, Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.config import get_settings
from app.core.exceptions import CSRFError, ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token, verify_csrf_token
from app.db.session import get_db
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.organization import Organization
from app.models.user import User


async def get_token_from_request(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> tuple[str, bool]:
    """
    Extracts access token from Authorization header or HttpOnly cookie.
    Returns (token, is_cookie_auth).
    """
    settings = get_settings()

    # 1. Check Authorization Bearer header
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            return token, False

    # 2. Check HttpOnly cookie
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if cookie_token:
        # Check CSRF on state-changing requests when using cookie-based auth
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            # Exempt auth login/register endpoints from CSRF check (bootstrap phase)
            if not request.url.path.endswith("/auth/login") and not request.url.path.endswith("/auth/register"):
                csrf_header = request.headers.get("X-CSRF-Token")
                csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
                if not verify_csrf_token(csrf_header, csrf_cookie):
                    raise CSRFError()
        return cookie_token, True

    raise UnauthorizedError("Authentication required.")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that extracts and validates the JWT token and fetches current user."""
    # We call our extractor manually with request and header
    auth_header = request.headers.get("Authorization")
    token, _ = await get_token_from_request(request, auth_header)

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token claims.")

    query = (
        select(User)
        .options(selectinload(User.memberships).selectinload(OrganizationMembership.organization))
        .where(User.id == user_id)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("User account not found.")

    if not user.is_active:
        raise UnauthorizedError("User account is inactive.")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency ensuring current user is active."""
    return current_user


async def get_current_active_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Dependency ensuring current user has superuser privileges."""
    if not current_user.is_superuser:
        raise ForbiddenError("Superuser privileges required.")
    return current_user


def require_organization_membership(
    org_id_param_name: str = "org_id",
) -> Callable:
    """
    Dependency factory that verifies the current user belongs to the target organization.
    Returns the OrganizationMembership.
    """
    async def _verify_membership(
        request: Request,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> OrganizationMembership:
        # Extract org_id from path params or request headers
        org_id = request.path_params.get(org_id_param_name) or request.headers.get("X-Organization-Id")
        if not org_id:
            raise ForbiddenError("Organization context is required.")

        # If user is superuser, grant access with a virtual or found membership
        query = (
            select(OrganizationMembership)
            .options(selectinload(OrganizationMembership.organization))
            .where(
                OrganizationMembership.user_id == current_user.id,
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.is_active == True,
            )
        )
        result = await db.execute(query)
        membership = result.scalar_one_or_none()

        if not membership:
            if current_user.is_superuser:
                # Fetch organization
                org = await db.get(Organization, org_id)
                if not org:
                    raise ForbiddenError(f"Organization '{org_id}' not found.")
                # Create ephemeral membership for superuser
                membership = OrganizationMembership(
                    id="superuser",
                    user_id=current_user.id,
                    organization_id=org_id,
                    role=OrganizationRole.ADMIN.value,
                    is_active=True,
                    organization=org,
                    user=current_user,
                )
                return membership
            raise ForbiddenError("You do not have access to this organization's resources.")

        return membership

    return _verify_membership


def require_role(allowed_roles: List[str], org_id_param_name: str = "org_id") -> Callable:
    """
    Dependency factory enforcing role-based access control (Admin, Analyst, Reviewer)
    within the specific organization context.
    """
    membership_checker = require_organization_membership(org_id_param_name)

    async def _verify_role(
        membership: OrganizationMembership = Depends(membership_checker),
    ) -> OrganizationMembership:
        # Normalize strings
        allowed_normalized = [r.lower() for r in allowed_roles]
        if membership.role.lower() not in allowed_normalized:
            raise ForbiddenError(
                f"Action requires one of [{', '.join(allowed_roles)}] role. "
                f"Current role: {membership.role}."
            )
        return membership

    return _verify_role
