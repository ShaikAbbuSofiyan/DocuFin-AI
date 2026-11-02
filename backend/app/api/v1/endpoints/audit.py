import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.api.v1.endpoints.documents import get_active_org_membership
from app.core.exceptions import ForbiddenError
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.user import User
from app.schemas.audit import AuditLogItem, PaginatedAuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get(
    "/audit/logs",
    response_model=PaginatedAuditLogResponse,
    summary="Search and retrieve immutable audit logs with organization scoping",
)
async def get_audit_logs_endpoint(
    action: Optional[str] = Query(None, description="Filter by event action (e.g. DOCUMENT_APPROVED, FIELD_CORRECTED)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type (DOCUMENT, REVIEW_TASK, EXTRACTION)"),
    resource_id: Optional[str] = Query(None, description="Filter by specific resource ID"),
    user_id: Optional[str] = Query(None, description="Filter by actor user ID"),
    date_from: Optional[datetime] = Query(None, description="Filter by timestamp from"),
    date_to: Optional[datetime] = Query(None, description="Filter by timestamp to"),
    search: Optional[str] = Query(None, description="Search pattern matching action, resource, or actor email"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Searchable, append-only audit trail strictly scoped to the active tenant organization.
    Restricted to Administrators and Reviewers for regulatory compliance.
    """
    if membership.role.lower() not in [
        OrganizationRole.ADMIN.value.lower(),
        OrganizationRole.REVIEWER.value.lower(),
    ] and not current_user.is_superuser:
        raise ForbiddenError("Only Administrators and Reviewers are authorized to view regulatory audit trails.")

    service = AuditService(db)
    items, total = await service.get_audit_logs(
        organization_id=membership.organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        page=page,
        page_size=page_size,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedAuditLogResponse(
        items=[AuditLogItem.model_validate(it) for it in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
