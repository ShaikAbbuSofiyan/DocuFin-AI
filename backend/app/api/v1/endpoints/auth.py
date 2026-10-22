import re
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_active_user
from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
    RateLimitExceededError,
    UnauthorizedError,
)
from app.core.logging import logger
from app.core.security import (
    check_and_record_login_attempt,
    create_access_token,
    generate_csrf_token,
    hash_password,
    reset_login_attempts,
    verify_password,
)
from app.db.session import get_db
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import (
    MessageResponse,
    OrganizationMembershipDetail,
    TokenResponse,
    UserLoginRequest,
    UserMeResponse,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter()


def _slugify(text: str) -> str:
    """Generate URL-safe slug from text."""
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug or "org"


def _set_auth_cookies(response: Response, access_token: str, csrf_token: str) -> None:
    """Attaches HttpOnly access token cookie and client-readable CSRF token cookie."""
    settings = get_settings()
    max_age = settings.jwt_access_token_expire_minutes * 60

    # HttpOnly, SameSite, Secure (in production/HTTPS) cookie for access token
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
    )

    # CSRF cookie readable by frontend JavaScript for double-submit header
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clears authentication cookies."""
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        domain=settings.auth_cookie_domain,
        path="/",
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        domain=settings.auth_cookie_domain,
        path="/",
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user and default organization",
)
async def register(
    request: Request,
    response: Response,
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Registers a new user, hashes password with Argon2id, and provisions
    their initial tenant organization with Admin role.
    """
    settings = get_settings()
    normalized_email = payload.email.strip().lower()

    # Check if user already exists
    existing_user_query = select(User).where(User.email == normalized_email)
    existing_user_res = await db.execute(existing_user_query)
    if existing_user_res.scalar_one_or_none():
        raise ConflictError(
            message="An account with this email address already exists.",
            details={"email": normalized_email},
        )

    # Hash password with Argon2
    hashed_pwd = hash_password(payload.password)

    # Create User
    user = User(
        email=normalized_email,
        hashed_password=hashed_pwd,
        full_name=payload.full_name.strip(),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()  # Populates user.id

    # Create initial organization
    org_name = payload.organization_name.strip() if payload.organization_name else f"{user.full_name}'s Organization"
    base_slug = _slugify(org_name)
    slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    org = Organization(
        name=org_name,
        slug=slug,
        is_active=True,
    )
    db.add(org)
    await db.flush()

    # Create organization membership with Admin role
    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org.id,
        role=OrganizationRole.ADMIN.value,
        is_active=True,
    )
    db.add(membership)
    await db.commit()

    # Issue JWT token and CSRF token
    access_token = create_access_token(
        subject=user.id,
        claims={"email": user.email, "org_id": org.id, "role": OrganizationRole.ADMIN.value},
    )
    csrf_token = generate_csrf_token()

    _set_auth_cookies(response, access_token, csrf_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and set session cookies",
)
async def login(
    request: Request,
    response: Response,
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticates user credentials, applies rate limiting against brute-force attacks,
    and returns session tokens and HttpOnly cookies.
    """
    settings = get_settings()
    normalized_email = payload.email.strip().lower()

    # Rate limiting key: combine client IP and email
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key = f"{client_ip}:{normalized_email}"

    is_allowed, remaining_sec = check_and_record_login_attempt(rate_limit_key)
    if not is_allowed:
        logger.warning(f"Rate limit exceeded for login attempt: {rate_limit_key}")
        raise RateLimitExceededError(
            message=f"Too many failed login attempts. Please wait {remaining_sec} seconds before trying again.",
            details={"retry_after_seconds": remaining_sec},
        )

    # Fetch user
    query = (
        select(User)
        .options(selectinload(User.memberships).selectinload(OrganizationMembership.organization))
        .where(User.email == normalized_email)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        # Do not distinguish between non-existent user and wrong password
        raise InvalidCredentialsError()

    if not user.is_active:
        raise UnauthorizedError("User account is inactive. Please contact support.")

    # Reset rate limiting counter on success
    reset_login_attempts(rate_limit_key)

    # Determine default organization and role
    primary_org_id = None
    primary_role = None
    for m in user.memberships:
        if m.is_active:
            primary_org_id = m.organization_id
            primary_role = m.role
            break

    access_token = create_access_token(
        subject=user.id,
        claims={"email": user.email, "org_id": primary_org_id, "role": primary_role},
    )
    csrf_token = generate_csrf_token()

    _set_auth_cookies(response, access_token, csrf_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user profile, organization memberships, and active context",
)
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
):
    """
    Returns current authenticated user details along with all active organization memberships
    and resolved active role.
    """
    memberships_detail: list[OrganizationMembershipDetail] = []
    active_org_id = None
    active_role = None

    for m in current_user.memberships:
        if m.is_active and m.organization and m.organization.is_active:
            detail = OrganizationMembershipDetail(
                id=m.id,
                organization_id=m.organization_id,
                organization_name=m.organization.name,
                organization_slug=m.organization.slug,
                role=m.role,
                is_active=m.is_active,
            )
            memberships_detail.append(detail)

            # Match requested active org or pick first
            if x_organization_id and m.organization_id == x_organization_id:
                active_org_id = m.organization_id
                active_role = m.role
            elif active_org_id is None:
                active_org_id = m.organization_id
                active_role = m.role

    # If requested specific org that wasn't found in normal memberships
    if x_organization_id and current_user.is_superuser and active_org_id != x_organization_id:
        active_org_id = x_organization_id
        active_role = OrganizationRole.ADMIN.value

    return UserMeResponse(
        user=UserResponse.model_validate(current_user),
        memberships=memberships_detail,
        active_organization_id=active_org_id,
        active_role=active_role,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out and invalidate session cookies",
)
async def logout(response: Response):
    """Clears authentication and CSRF cookies."""
    _clear_auth_cookies(response)
    return MessageResponse(message="Successfully logged out.")
