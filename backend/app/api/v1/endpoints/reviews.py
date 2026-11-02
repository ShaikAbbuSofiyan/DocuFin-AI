import math
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.api.v1.endpoints.documents import get_active_org_membership
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.review_task import ReviewTaskPriority, ReviewTaskStatus
from app.models.user import User
from app.schemas.review import (
    ApproveReviewTaskRequest,
    AssignReviewTaskRequest,
    CorrectFieldsRequest,
    CreateReviewTaskRequest,
    PaginatedReviewQueueResponse,
    RejectReviewTaskRequest,
    ReviewHistoryItem,
    ReviewTaskDetailResponse,
    ReviewTaskQueueItem,
)
from app.services.review_service import ReviewWorkflowService

router = APIRouter()


@router.get(
    "/reviews/queue",
    response_model=PaginatedReviewQueueResponse,
    summary="List review queue tasks with filters for status, type, date, and assigned reviewer",
)
async def get_review_queue_endpoint(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, IN_REVIEW, APPROVED, REJECTED"),
    document_type: Optional[str] = Query(None, description="Filter by document type (INVOICE, BANK_STATEMENT, etc.)"),
    assigned_to_id: Optional[str] = Query(None, description="Filter by assigned reviewer user ID"),
    date_from: Optional[datetime] = Query(None, description="Filter by creation date from"),
    date_to: Optional[datetime] = Query(None, description="Filter by creation date to"),
    search: Optional[str] = Query(None, description="Search by document title or filename"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a paginated and filterable human review queue for the tenant organization.
    Prioritizes high-risk documents and validation errors.
    """
    service = ReviewWorkflowService(db)
    items, total = await service.get_review_queue(
        organization_id=membership.organization_id,
        status=status,
        document_type=document_type,
        assigned_to_id=assigned_to_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedReviewQueueResponse(
        items=[ReviewTaskQueueItem(**it) for it in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/reviews",
    response_model=ReviewTaskDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or queue a document review task",
)
async def create_review_task_endpoint(
    payload: CreateReviewTaskRequest,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Queues a review task for a document and its latest extraction.
    """
    service = ReviewWorkflowService(db)
    task = await service.create_or_get_review_task(
        document_id=payload.document_id,
        organization_id=membership.organization_id,
        created_by_id=current_user.id,
        review_reasons=payload.review_reasons,
        priority=payload.priority or ReviewTaskPriority.MEDIUM.value,
    )
    return await service.get_review_task_detail(task.id, membership.organization_id)


@router.get(
    "/reviews/{task_id}",
    response_model=ReviewTaskDetailResponse,
    summary="Inspect review workspace details, extracted data, validation checks, and history",
)
async def get_review_task_detail_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns complete workspace details for side-by-side verification:
    original document metadata, extracted fields, validation results, and version.
    """
    service = ReviewWorkflowService(db)
    task = await service.get_review_task_detail(task_id, membership.organization_id)

    doc = task.document
    ext = task.extraction
    assignee = task.assigned_to

    return ReviewTaskDetailResponse(
        id=task.id,
        document_id=task.document_id,
        extraction_id=task.extraction_id,
        organization_id=task.organization_id,
        status=task.status,
        priority=task.priority,
        assigned_to_id=task.assigned_to_id,
        assigned_to_name=assignee.full_name if assignee else None,
        assigned_to_email=assignee.email if assignee else None,
        version=task.version,
        due_date=task.due_date,
        completed_at=task.completed_at,
        review_reasons=task.review_reasons,
        validation_error_count=task.validation_error_count,
        resolution_notes=task.resolution_notes,
        rejection_reason=task.rejection_reason,
        created_at=task.created_at,
        updated_at=task.updated_at,
        document_title=doc.title if doc else None,
        document_filename=doc.filename if doc else None,
        document_type=doc.doc_type if doc else None,
        uploader_id=doc.uploader_id if doc else None,
        extracted_data=ext.extracted_data if ext else {},
        field_metadata=ext.field_metadata if ext else {},
        validation_errors=ext.validation_errors if ext else [],
        histories=[ReviewHistoryItem.model_validate(h) for h in (task.histories or [])],
    )


@router.post(
    "/reviews/{task_id}/assign",
    response_model=ReviewTaskDetailResponse,
    summary="Assign review task to a specific reviewer or self",
)
async def assign_review_task_endpoint(
    task_id: str,
    payload: AssignReviewTaskRequest,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """Assigns the task to an analyst or reviewer. Enforces role authorization."""
    service = ReviewWorkflowService(db)
    await service.assign_review_task(
        task_id=task_id,
        organization_id=membership.organization_id,
        assigned_to_id=payload.assigned_to_id,
        current_user=current_user,
        current_role=membership.role,
    )
    return await get_review_task_detail_endpoint(task_id, current_user, membership, db)


@router.post(
    "/reviews/{task_id}/correct",
    response_model=ReviewTaskDetailResponse,
    summary="Submit field corrections with optimistic concurrency locking and validation re-check",
)
async def correct_review_fields_endpoint(
    task_id: str,
    payload: CorrectFieldsRequest,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Applies reviewer field edits, saves previous and updated values in history,
    re-validates math rules, and increments the task version.
    """
    service = ReviewWorkflowService(db)
    await service.correct_extracted_fields(
        task_id=task_id,
        organization_id=membership.organization_id,
        field_updates=payload.field_updates,
        notes=payload.notes,
        expected_version=payload.expected_version,
        current_user=current_user,
        current_role=membership.role,
    )
    return await get_review_task_detail_endpoint(task_id, current_user, membership, db)


@router.post(
    "/reviews/{task_id}/approve",
    response_model=ReviewTaskDetailResponse,
    summary="Approve document and complete review task enforcing dual control policy",
)
async def approve_review_task_endpoint(
    task_id: str,
    payload: ApproveReviewTaskRequest,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Approves document, transitions status to APPROVED, records decisions,
    and enforces dual-control policy prohibiting self-approval.
    """
    service = ReviewWorkflowService(db)
    await service.approve_review_task(
        task_id=task_id,
        organization_id=membership.organization_id,
        notes=payload.notes,
        expected_version=payload.expected_version,
        current_user=current_user,
        current_role=membership.role,
    )
    return await get_review_task_detail_endpoint(task_id, current_user, membership, db)


@router.post(
    "/reviews/{task_id}/reject",
    response_model=ReviewTaskDetailResponse,
    summary="Reject document with mandatory explanation notes",
)
async def reject_review_task_endpoint(
    task_id: str,
    payload: RejectReviewTaskRequest,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Rejects document with required reason, transitions status to REJECTED,
    and appends immutable audit events.
    """
    service = ReviewWorkflowService(db)
    await service.reject_review_task(
        task_id=task_id,
        organization_id=membership.organization_id,
        rejection_reason=payload.rejection_reason,
        expected_version=payload.expected_version,
        current_user=current_user,
        current_role=membership.role,
    )
    return await get_review_task_detail_endpoint(task_id, current_user, membership, db)


@router.get(
    "/reviews/{task_id}/history",
    response_model=List[ReviewHistoryItem],
    summary="Get chronological decision history and field diffs for a review task",
)
async def get_review_history_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full audit timeline of who modified or approved the task, with previous and new values."""
    service = ReviewWorkflowService(db)
    histories = await service.get_task_history(task_id, membership.organization_id)
    return [ReviewHistoryItem.model_validate(h) for h in histories]
