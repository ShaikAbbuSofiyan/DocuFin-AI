import re
import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import (
    get_current_active_user,
    require_organization_membership,
    require_role,
)
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.organization import (
    AddMemberRequest,
    OrganizationCreateRequest,
    OrganizationMemberResponse,
    OrganizationResponse,
    UpdateMemberRoleRequest,
)

router = APIRouter()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug or "org"


@router.get(
    "/",
    response_model=List[OrganizationResponse],
    summary="List all organizations the user belongs to",
)
async def list_user_organizations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns organizations where the user has an active membership."""
    query = (
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.is_active == True,
            Organization.is_active == True,
        )
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_organization(
    payload: OrganizationCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new organization and grants current user the Admin role."""
    base_slug = payload.slug or _slugify(payload.name)
    slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    org = Organization(
        name=payload.name.strip(),
        slug=slug,
        is_active=True,
    )
    db.add(org)
    await db.flush()

    membership = OrganizationMembership(
        user_id=current_user.id,
        organization_id=org.id,
        role=OrganizationRole.ADMIN.value,
        is_active=True,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(org)

    return org


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization details (requires membership)",
)
async def get_organization(
    org_id: str,
    membership: OrganizationMembership = Depends(require_organization_membership("org_id")),
):
    """Returns organization metadata for authorized members."""
    return membership.organization


@router.get(
    "/{org_id}/members",
    response_model=List[OrganizationMemberResponse],
    summary="List members in an organization (requires membership)",
)
async def list_organization_members(
    org_id: str,
    membership: OrganizationMembership = Depends(require_organization_membership("org_id")),
    db: AsyncSession = Depends(get_db),
):
    """Returns all active members in the organization."""
    query = (
        select(OrganizationMembership)
        .options(selectinload(OrganizationMembership.user))
        .where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.is_active == True,
        )
    )
    result = await db.execute(query)
    memberships = result.scalars().all()

    return [
        OrganizationMemberResponse(
            id=m.id,
            user_id=m.user_id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role,
            is_active=m.is_active,
            created_at=m.created_at,
        )
        for m in memberships
        if m.user
    ]


@router.post(
    "/{org_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a user to an organization (Admin only)",
)
async def add_organization_member(
    org_id: str,
    payload: AddMemberRequest,
    membership: OrganizationMembership = Depends(require_role([OrganizationRole.ADMIN.value], "org_id")),
    db: AsyncSession = Depends(get_db),
):
    """Assigns an existing user to this organization. Requires Admin role."""
    target_role = payload.role.strip().capitalize()
    valid_roles = [r.value for r in OrganizationRole]
    if target_role not in valid_roles:
        raise ConflictError(
            message=f"Invalid role '{payload.role}'. Must be one of {valid_roles}.",
            details={"allowed_roles": valid_roles},
        )

    # Find target user by email
    target_user_query = select(User).where(User.email == payload.email.strip().lower())
    target_user_res = await db.execute(target_user_query)
    target_user = target_user_res.scalar_one_or_none()
    if not target_user:
        raise NotFoundError("User with email", payload.email)

    # Check existing membership
    existing_mem_query = select(OrganizationMembership).where(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == target_user.id,
    )
    existing_mem_res = await db.execute(existing_mem_query)
    existing_mem = existing_mem_res.scalar_one_or_none()

    if existing_mem:
        if existing_mem.is_active:
            raise ConflictError("User is already an active member of this organization.")
        # Reactivate
        existing_mem.is_active = True
        existing_mem.role = target_role
        await db.commit()
        await db.refresh(existing_mem)
        new_membership = existing_mem
    else:
        new_membership = OrganizationMembership(
            user_id=target_user.id,
            organization_id=org_id,
            role=target_role,
            is_active=True,
        )
        db.add(new_membership)
        await db.commit()
        await db.refresh(new_membership)

    return OrganizationMemberResponse(
        id=new_membership.id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=new_membership.role,
        is_active=new_membership.is_active,
        created_at=new_membership.created_at,
    )


@router.patch(
    "/{org_id}/members/{user_id}",
    response_model=OrganizationMemberResponse,
    summary="Update member role (Admin only)",
)
async def update_member_role(
    org_id: str,
    user_id: str,
    payload: UpdateMemberRoleRequest,
    membership: OrganizationMembership = Depends(require_role([OrganizationRole.ADMIN.value], "org_id")),
    db: AsyncSession = Depends(get_db),
):
    """Updates a user's role in the organization. Requires Admin role."""
    target_role = payload.role.strip().capitalize()
    valid_roles = [r.value for r in OrganizationRole]
    if target_role not in valid_roles:
        raise ConflictError(f"Invalid role. Must be one of {valid_roles}.")

    query = (
        select(OrganizationMembership)
        .options(selectinload(OrganizationMembership.user))
        .where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.is_active == True,
        )
    )
    res = await db.execute(query)
    target_mem = res.scalar_one_or_none()
    if not target_mem:
        raise NotFoundError("Organization membership for user", user_id)

    target_mem.role = target_role
    await db.commit()
    await db.refresh(target_mem)

    return OrganizationMemberResponse(
        id=target_mem.id,
        user_id=target_mem.user_id,
        email=target_mem.user.email,
        full_name=target_mem.user.full_name,
        role=target_mem.role,
        is_active=target_mem.is_active,
        created_at=target_mem.created_at,
    )


@router.delete(
    "/{org_id}/members/{user_id}",
    response_model=MessageResponse,
    summary="Remove a user from an organization (Admin only)",
)
async def remove_organization_member(
    org_id: str,
    user_id: str,
    membership: OrganizationMembership = Depends(require_role([OrganizationRole.ADMIN.value], "org_id")),
    db: AsyncSession = Depends(get_db),
):
    """Removes a user from the organization. Cannot remove the last Admin."""
    query = (
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.is_active == True,
        )
    )
    res = await db.execute(query)
    target_mem = res.scalar_one_or_none()
    if not target_mem:
        raise NotFoundError("Active membership for user", user_id)

    # If target is Admin, ensure there's at least one other active Admin
    if target_mem.role == OrganizationRole.ADMIN.value:
        admin_count_query = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.role == OrganizationRole.ADMIN.value,
            OrganizationMembership.is_active == True,
        )
        admin_res = await db.execute(admin_count_query)
        admins = admin_res.scalars().all()
        if len(admins) <= 1:
            raise ForbiddenError("Cannot remove the only administrator of the organization.")

    target_mem.is_active = False
    await db.commit()

    return MessageResponse(message="Member removed successfully.")
