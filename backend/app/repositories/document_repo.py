from typing import List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.document import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository handling database operations for Document entities with multi-tenant filtering."""

    def __init__(self, session: AsyncSession):
        super().__init__(Document, session)

    async def get_by_id_scoped(self, doc_id: str, org_id: str) -> Optional[Document]:
        """Fetch a document by ID ensuring strict organization isolation."""
        stmt = (
            select(Document)
            .where(Document.id == doc_id, Document.organization_id == org_id)
            .options(selectinload(Document.uploader))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def search_and_paginate(
        self,
        org_id: str,
        search: Optional[str] = None,
        status: Optional[str] = None,
        doc_type: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Document], int]:
        """
        Retrieves paginated, filtered, searched, and sorted documents strictly scoped to an organization.
        """
        # Base filter condition
        base_filters = [Document.organization_id == org_id]

        if status:
            base_filters.append(Document.status == status.upper())

        if doc_type:
            base_filters.append(Document.doc_type == doc_type.upper())

        if search and search.strip():
            term = f"%{search.strip()}%"
            base_filters.append(
                or_(
                    Document.title.ilike(term),
                    Document.filename.ilike(term),
                )
            )

        # 1. Total count query
        count_stmt = select(func.count(Document.id)).where(*base_filters)
        total_res = await self.session.execute(count_stmt)
        total_count = total_res.scalar_one_or_none() or 0

        # 2. Sorting
        sort_column = getattr(Document, sort_by, Document.created_at)
        if sort_order.lower() == "asc":
            order_clause = sort_column.asc()
        else:
            order_clause = sort_column.desc()

        # 3. Data query with pagination
        offset = max(0, (page - 1) * page_size)
        data_stmt = (
            select(Document)
            .where(*base_filters)
            .order_by(order_clause)
            .offset(offset)
            .limit(page_size)
            .options(selectinload(Document.uploader))
        )
        result = await self.session.execute(data_stmt)
        items = list(result.scalars().all())

        return items, total_count
