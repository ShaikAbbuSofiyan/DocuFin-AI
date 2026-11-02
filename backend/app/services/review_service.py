import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.document import Document, DocumentStatus
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.schemas.extraction import ExtractionMethod
from app.models.membership import OrganizationRole
from app.models.review_history import ReviewHistory
from app.models.review_task import ReviewTask, ReviewTaskPriority, ReviewTaskStatus
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.validation_engine import FinancialValidationEngine
from app.services.state_machine import validate_document_transition, validate_review_task_transition

logger = logging.getLogger("docufin.review_service")


class ReviewWorkflowService:
    """
    Manages human-in-the-loop document reviews, field-level corrections with change tracking,
    dual-control approval policies, and optimistic concurrency locking.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.audit_service = AuditService(db)

    async def create_or_get_review_task(
        self,
        document_id: str,
        organization_id: str,
        created_by_id: Optional[str] = None,
        review_reasons: Optional[List[str]] = None,
        priority: str = ReviewTaskPriority.MEDIUM.value,
    ) -> ReviewTask:
        """
        Creates a new ReviewTask for a document if one does not already exist,
        or retrieves the existing active task.
        """
        # 1. Verify document exists and belongs to organization
        doc_query = select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
        doc_res = await self.db.execute(doc_query)
        doc = doc_res.scalar_one_or_none()
        if not doc:
            raise NotFoundError("Document", document_id)

        # 2. Check for existing review task
        task_query = (
            select(ReviewTask)
            .where(
                ReviewTask.document_id == document_id,
                ReviewTask.organization_id == organization_id,
                ReviewTask.status.in_([ReviewTaskStatus.PENDING.value, ReviewTaskStatus.IN_REVIEW.value]),
            )
            .order_by(desc(ReviewTask.created_at))
            .limit(1)
        )
        task_res = await self.db.execute(task_query)
        existing_task = task_res.scalar_one_or_none()
        if existing_task:
            return existing_task

        # 3. Find latest extraction
        ext_query = (
            select(DocumentExtraction)
            .where(
                DocumentExtraction.document_id == document_id,
                DocumentExtraction.organization_id == organization_id,
            )
            .order_by(desc(DocumentExtraction.created_at))
            .limit(1)
        )
        ext_res = await self.db.execute(ext_query)
        latest_ext = ext_res.scalar_one_or_none()

        error_count = len(latest_ext.validation_errors) if latest_ext and latest_ext.validation_errors else 0
        reasons = review_reasons or (latest_ext.review_reasons if latest_ext else [])

        # Assign priority based on errors
        if error_count > 3:
            priority = ReviewTaskPriority.CRITICAL.value
        elif error_count > 0:
            priority = ReviewTaskPriority.HIGH.value

        task = ReviewTask(
            document_id=document_id,
            extraction_id=latest_ext.id if latest_ext else None,
            organization_id=organization_id,
            status=ReviewTaskStatus.PENDING.value,
            priority=priority,
            created_by_id=created_by_id,
            version=1,
            review_reasons=reasons,
            validation_error_count=error_count,
        )
        self.db.add(task)
        await self.db.flush()

        # Update document status to REVIEW_REQUIRED if not already
        if doc.status not in [DocumentStatus.REVIEW_REQUIRED.value, DocumentStatus.APPROVED.value]:
            validate_document_transition(doc.status, DocumentStatus.REVIEW_REQUIRED.value)
            doc.status = DocumentStatus.REVIEW_REQUIRED.value

        # Log creation history
        history = ReviewHistory(
            review_task_id=task.id,
            document_id=document_id,
            organization_id=organization_id,
            user_id=created_by_id,
            action="CREATED",
            new_status=ReviewTaskStatus.PENDING.value,
            notes=f"Review task queued with priority {priority}",
        )
        self.db.add(history)

        await self.audit_service.log_event(
            organization_id=organization_id,
            action="REVIEW_TASK_CREATED",
            resource_type="REVIEW_TASK",
            resource_id=task.id,
            user_id=created_by_id,
            details={"document_id": document_id, "priority": priority, "error_count": error_count},
        )

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_review_queue(
        self,
        organization_id: str,
        status: Optional[str] = None,
        document_type: Optional[str] = None,
        assigned_to_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieves a filtered and paginated review queue strictly isolated by organization.
        """
        query = (
            select(ReviewTask, Document, DocumentExtraction, User)
            .join(Document, ReviewTask.document_id == Document.id)
            .outerjoin(DocumentExtraction, ReviewTask.extraction_id == DocumentExtraction.id)
            .outerjoin(User, ReviewTask.assigned_to_id == User.id)
            .where(ReviewTask.organization_id == organization_id)
        )

        if status:
            query = query.where(ReviewTask.status == status)
        if document_type:
            query = query.where(Document.doc_type == document_type)
        if assigned_to_id:
            query = query.where(ReviewTask.assigned_to_id == assigned_to_id)
        if date_from:
            query = query.where(ReviewTask.created_at >= date_from)
        if date_to:
            query = query.where(ReviewTask.created_at <= date_to)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Document.title.ilike(search_pattern),
                    Document.filename.ilike(search_pattern),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar_one() or 0

        # Sort: CRITICAL/HIGH priority first, then created_at
        offset = (page - 1) * page_size
        results_stmt = (
            query.order_by(
                desc(ReviewTask.priority == ReviewTaskPriority.CRITICAL.value),
                desc(ReviewTask.priority == ReviewTaskPriority.HIGH.value),
                desc(ReviewTask.created_at),
            )
            .offset(offset)
            .limit(page_size)
        )
        rows_res = await self.db.execute(results_stmt)
        rows = rows_res.all()

        queue_items = []
        for task, doc, ext, assignee in rows:
            queue_items.append({
                "id": task.id,
                "document_id": doc.id,
                "document_title": doc.title,
                "document_filename": doc.filename,
                "document_type": doc.doc_type,
                "extraction_id": ext.id if ext else None,
                "status": task.status,
                "priority": task.priority,
                "version": task.version,
                "assigned_to_id": task.assigned_to_id,
                "assigned_to_name": assignee.full_name if assignee else None,
                "assigned_to_email": assignee.email if assignee else None,
                "review_reasons": task.review_reasons,
                "validation_error_count": task.validation_error_count,
                "confidence_score": ext.confidence_score if ext else 0.0,
                "due_date": task.due_date,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            })

        return queue_items, total

    async def get_review_task_detail(
        self,
        task_id: str,
        organization_id: str,
    ) -> ReviewTask:
        """
        Retrieves complete review task with relations, enforcing tenant isolation.
        """
        query = (
            select(ReviewTask)
            .options(
                selectinload(ReviewTask.document),
                selectinload(ReviewTask.extraction),
                selectinload(ReviewTask.assigned_to),
                selectinload(ReviewTask.created_by),
                selectinload(ReviewTask.histories),
            )
            .where(
                ReviewTask.id == task_id,
                ReviewTask.organization_id == organization_id,
            )
        )
        res = await self.db.execute(query)
        task = res.scalar_one_or_none()
        if not task:
            raise NotFoundError("ReviewTask", task_id)
        return task

    async def assign_review_task(
        self,
        task_id: str,
        organization_id: str,
        assigned_to_id: Optional[str],
        current_user: User,
        current_role: str,
    ) -> ReviewTask:
        """
        Assigns or unassigns a review task to an authorized reviewer.
        Transitions status from PENDING to IN_REVIEW when assigned.
        """
        task = await self.get_review_task_detail(task_id, organization_id)

        # Only Admins and Reviewers can assign tasks
        if current_role.lower() not in [OrganizationRole.ADMIN.value.lower(), OrganizationRole.REVIEWER.value.lower()]:
            raise ForbiddenError("Only Administrators and Reviewers can assign review tasks.")

        old_assignee_id = task.assigned_to_id
        task.assigned_to_id = assigned_to_id

        # Update status if assigning from PENDING
        if assigned_to_id and task.status == ReviewTaskStatus.PENDING.value:
            validate_review_task_transition(task.status, ReviewTaskStatus.IN_REVIEW.value)
            task.status = ReviewTaskStatus.IN_REVIEW.value

        task.version += 1

        # Record History
        history = ReviewHistory(
            review_task_id=task.id,
            document_id=task.document_id,
            organization_id=organization_id,
            user_id=current_user.id,
            user_email=current_user.email,
            user_role=current_role,
            action="ASSIGNED",
            notes=f"Reassigned from {old_assignee_id or 'None'} to {assigned_to_id or 'Unassigned'}",
        )
        self.db.add(history)

        await self.audit_service.log_event(
            organization_id=organization_id,
            action="REVIEW_TASK_ASSIGNED",
            resource_type="REVIEW_TASK",
            resource_id=task.id,
            user_id=current_user.id,
            user_email=current_user.email,
            details={"previous_assignee": old_assignee_id, "new_assignee": assigned_to_id},
        )

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def correct_extracted_fields(
        self,
        task_id: str,
        organization_id: str,
        field_updates: Dict[str, Any],
        notes: Optional[str],
        expected_version: int,
        current_user: User,
        current_role: str,
    ) -> Tuple[ReviewTask, DocumentExtraction]:
        """
        Applies reviewer field corrections, tracks old vs new values in review history,
        re-runs validation engine, and enforces optimistic concurrency locking.
        """
        task = await self.get_review_task_detail(task_id, organization_id)

        # 1. Optimistic locking / concurrency check
        if task.version != expected_version:
            raise ConflictError(
                f"Concurrent modification detected. Review task is currently at version {task.version}, "
                f"but you submitted version {expected_version}. Please reload the latest changes.",
                details={"current_version": task.version, "submitted_version": expected_version},
            )

        if not task.extraction:
            raise ValidationError("Review task has no linked structured extraction to correct.")

        extraction = task.extraction
        current_data = dict(extraction.extracted_data or {})
        field_changes: Dict[str, Dict[str, Any]] = {}

        # 2. Compute field diffs (previous value vs updated value)
        for key, new_val in field_updates.items():
            old_val = current_data.get(key)
            if old_val != new_val:
                field_changes[key] = {
                    "old_value": old_val,
                    "new_value": new_val,
                }
                current_data[key] = new_val

        if not field_changes:
            return task, extraction  # No changes made

        extraction.extracted_data = current_data

        # 3. Update field metadata to MANUAL and 1.0 confidence
        meta = dict(extraction.field_metadata or {})
        for field_name in field_changes:
            field_meta = dict(meta.get(field_name, {}))
            field_meta["value"] = current_data[field_name]
            field_meta["extraction_method"] = ExtractionMethod.MANUAL.value
            field_meta["confidence"] = 1.0
            meta[field_name] = field_meta
        extraction.field_metadata = meta

        # 4. Re-run business validation on corrected figures
        engine = FinancialValidationEngine(
            rounding_tolerance=self.settings.validation_rounding_tolerance,
            default_currency_precision=self.settings.validation_default_currency_precision,
            strict_mode=self.settings.validation_strict_mode,
        )
        val_summary, _ = await engine.validate_document_extraction(
            db=self.db,
            document_id=task.document_id,
            organization_id=organization_id,
            document_type=extraction.document_type,
            extracted_data=current_data,
            extraction_id=extraction.id,
            triggered_by="HUMAN_REVIEW_CORRECTION",
        )

        extraction.is_valid = val_summary.is_valid
        extraction.validation_errors = [r.model_dump() for r in val_summary.results]
        extraction.reviewed_by_id = current_user.id
        extraction.reviewed_at = datetime.now(timezone.utc)
        if notes:
            extraction.analyst_notes = notes

        task.validation_error_count = val_summary.error_count
        task.version += 1

        # 5. Record Review History entry with field changes
        history = ReviewHistory(
            review_task_id=task.id,
            document_id=task.document_id,
            organization_id=organization_id,
            user_id=current_user.id,
            user_email=current_user.email,
            user_role=current_role,
            action="FIELD_CORRECTION",
            field_changes=field_changes,
            notes=notes,
        )
        self.db.add(history)

        # 6. Append-only audit log
        await self.audit_service.log_event(
            organization_id=organization_id,
            action="EXTRACTION_FIELD_CORRECTED",
            resource_type="EXTRACTION",
            resource_id=extraction.id,
            user_id=current_user.id,
            user_email=current_user.email,
            details={
                "task_id": task.id,
                "fields_modified": list(field_changes.keys()),
                "field_changes": field_changes,
                "validation_passed": val_summary.is_valid,
            },
        )

        await self.db.commit()
        await self.db.refresh(task)
        await self.db.refresh(extraction)
        return task, extraction

    async def approve_review_task(
        self,
        task_id: str,
        organization_id: str,
        notes: Optional[str],
        expected_version: int,
        current_user: User,
        current_role: str,
    ) -> ReviewTask:
        """
        Approves a document and marks review task completed.
        Enforces role-based permissions, dual-control policy (prohibiting self-approval),
        explicit state transitions, and concurrency locking.
        """
        task = await self.get_review_task_detail(task_id, organization_id)

        # 1. Role-based review permissions: Analysts cannot make final approval
        if current_role.lower() not in [OrganizationRole.ADMIN.value.lower(), OrganizationRole.REVIEWER.value.lower()]:
            raise ForbiddenError("Only Administrators and Reviewers can approve document review tasks.")

        # 2. Optimistic locking check
        if task.version != expected_version:
            raise ConflictError(
                f"Concurrent modification detected. Review task is at version {task.version}, "
                f"but you submitted version {expected_version}. Please reload the latest state.",
                details={"current_version": task.version, "submitted_version": expected_version},
            )

        # 3. Segregation of Duties / Dual Control Policy
        if self.settings.review_enforce_dual_control:
            # Policy Rule 1: The uploader cannot approve their own document
            if task.document and task.document.uploader_id and task.document.uploader_id == current_user.id:
                raise ForbiddenError(
                    "Self-approval policy violation: You cannot approve a document you uploaded. "
                    "Dual control requires a distinct authorized reviewer or administrator to approve."
                )

            # Policy Rule 2: The user who made the latest manual corrections cannot approve their own corrections
            if task.extraction and task.extraction.reviewed_by_id and task.extraction.reviewed_by_id == current_user.id:
                # If there are active manual field changes made by this user, require a second reviewer
                hist_query = (
                    select(ReviewHistory)
                    .where(
                        ReviewHistory.review_task_id == task.id,
                        ReviewHistory.action == "FIELD_CORRECTION",
                    )
                    .order_by(desc(ReviewHistory.created_at))
                    .limit(1)
                )
                h_res = await self.db.execute(hist_query)
                last_correction = h_res.scalar_one_or_none()
                if last_correction and last_correction.user_id == current_user.id:
                    raise ForbiddenError(
                        "Self-approval policy violation: You cannot approve your own manual corrections. "
                        "A distinct reviewer or administrator must verify the changes."
                    )

        # 4. Validated state transitions
        old_doc_status = task.document.status
        validate_document_transition(old_doc_status, DocumentStatus.APPROVED.value)
        validate_review_task_transition(task.status, ReviewTaskStatus.APPROVED.value)

        # 5. Apply transitions
        task.document.status = DocumentStatus.APPROVED.value
        task.status = ReviewTaskStatus.APPROVED.value
        task.completed_at = datetime.now(timezone.utc)
        task.resolution_notes = notes
        task.version += 1

        if task.extraction:
            task.extraction.status = ExtractionStatus.APPROVED.value
            task.extraction.needs_review = False
            task.extraction.confidence_score = 1.0

        # 6. Record Review History
        history = ReviewHistory(
            review_task_id=task.id,
            document_id=task.document_id,
            organization_id=organization_id,
            user_id=current_user.id,
            user_email=current_user.email,
            user_role=current_role,
            action="APPROVED",
            previous_status=old_doc_status,
            new_status=DocumentStatus.APPROVED.value,
            notes=notes,
        )
        self.db.add(history)

        # 7. Append-only Audit Log
        await self.audit_service.log_event(
            organization_id=organization_id,
            action="DOCUMENT_APPROVED",
            resource_type="DOCUMENT",
            resource_id=task.document_id,
            user_id=current_user.id,
            user_email=current_user.email,
            details={
                "task_id": task.id,
                "previous_status": old_doc_status,
                "new_status": DocumentStatus.APPROVED.value,
                "notes": notes,
                "reviewer_role": current_role,
            },
        )

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def reject_review_task(
        self,
        task_id: str,
        organization_id: str,
        rejection_reason: str,
        expected_version: int,
        current_user: User,
        current_role: str,
    ) -> ReviewTask:
        """
        Rejects a document with a mandatory rejection reason.
        Enforces permissions, explicit state transitions, and concurrency locking.
        """
        task = await self.get_review_task_detail(task_id, organization_id)

        # 1. Role-based review permissions
        if current_role.lower() not in [OrganizationRole.ADMIN.value.lower(), OrganizationRole.REVIEWER.value.lower()]:
            raise ForbiddenError("Only Administrators and Reviewers can reject document review tasks.")

        # 2. Mandatory rejection reason
        if not rejection_reason or not rejection_reason.strip():
            raise ValidationError("A clear rejection reason is mandatory when rejecting a financial document.")

        # 3. Optimistic locking check
        if task.version != expected_version:
            raise ConflictError(
                f"Concurrent modification detected. Review task is at version {task.version}, "
                f"but you submitted version {expected_version}. Please reload the latest state.",
                details={"current_version": task.version, "submitted_version": expected_version},
            )

        # 4. Validated state transitions
        old_doc_status = task.document.status
        validate_document_transition(old_doc_status, DocumentStatus.REJECTED.value)
        validate_review_task_transition(task.status, ReviewTaskStatus.REJECTED.value)

        # 5. Apply transitions
        task.document.status = DocumentStatus.REJECTED.value
        task.status = ReviewTaskStatus.REJECTED.value
        task.completed_at = datetime.now(timezone.utc)
        task.rejection_reason = rejection_reason.strip()
        task.version += 1

        if task.extraction:
            task.extraction.status = ExtractionStatus.REJECTED.value
            task.extraction.needs_review = False

        # 6. Record Review History
        history = ReviewHistory(
            review_task_id=task.id,
            document_id=task.document_id,
            organization_id=organization_id,
            user_id=current_user.id,
            user_email=current_user.email,
            user_role=current_role,
            action="REJECTED",
            previous_status=old_doc_status,
            new_status=DocumentStatus.REJECTED.value,
            notes=rejection_reason.strip(),
        )
        self.db.add(history)

        # 7. Append-only Audit Log
        await self.audit_service.log_event(
            organization_id=organization_id,
            action="DOCUMENT_REJECTED",
            resource_type="DOCUMENT",
            resource_id=task.document_id,
            user_id=current_user.id,
            user_email=current_user.email,
            details={
                "task_id": task.id,
                "previous_status": old_doc_status,
                "new_status": DocumentStatus.REJECTED.value,
                "rejection_reason": rejection_reason.strip(),
                "reviewer_role": current_role,
            },
        )

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_task_history(
        self,
        task_id: str,
        organization_id: str,
    ) -> List[ReviewHistory]:
        """
        Retrieves complete chronological audit history for a review task.
        """
        # Ensure task belongs to organization
        await self.get_review_task_detail(task_id, organization_id)

        query = (
            select(ReviewHistory)
            .where(
                ReviewHistory.review_task_id == task_id,
                ReviewHistory.organization_id == organization_id,
            )
            .order_by(desc(ReviewHistory.created_at))
        )
        res = await self.db.execute(query)
        return list(res.scalars().all())
