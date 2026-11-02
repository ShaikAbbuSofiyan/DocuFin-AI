import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog

logger = logging.getLogger("docufin.audit")


class AuditService:
    """
    Append-only regulatory audit service for financial intelligence actions.
    Persists all transitions, corrections, assignments, and approvals to the database.
    Strictly isolated per tenant organization.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        organization_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Creates an immutable, append-only audit event in the database.
        """
        audit_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            details=details or {},
        )
        self.db.add(audit_entry)
        await self.db.flush()
        logger.info(
            f"Audit log recorded: org={organization_id} action={action} "
            f"resource={resource_type}:{resource_id} user={user_email or user_id}"
        )
        return audit_entry

    async def get_audit_logs(
        self,
        organization_id: str,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AuditLog], int]:
        """
        Retrieves paginated, filtered audit logs strictly scoped to organization.
        """
        query = select(AuditLog).where(AuditLog.organization_id == organization_id)

        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if date_from:
            query = query.where(AuditLog.created_at >= date_from)
        if date_to:
            query = query.where(AuditLog.created_at <= date_to)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    AuditLog.action.ilike(search_pattern),
                    AuditLog.resource_id.ilike(search_pattern),
                    AuditLog.user_email.ilike(search_pattern),
                )
            )

        # Count total matches
        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar_one() or 0

        # Paginate results
        offset = (page - 1) * page_size
        results_stmt = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(page_size)
        rows_res = await self.db.execute(results_stmt)
        items = list(rows_res.scalars().all())

        return items, total
