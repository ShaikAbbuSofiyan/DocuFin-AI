import math
import uuid
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundError, ValidationError
from app.core.file_validation import validate_file_content
from app.core.logging import logger
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import (
    DocumentResponse,
    DocumentUpdate,
    PaginatedDocumentResponse,
)
from app.services.storage import get_storage_service
from app.services.storage.base import StorageService


class DocumentService:
    """Service layer managing secure document ingestion, storage, retrieval, and lifecycle."""

    def __init__(self, db: AsyncSession, storage: Optional[StorageService] = None):
        self.db = db
        self.repo = DocumentRepository(db)
        self.storage = storage or get_storage_service()

    async def upload_document(
        self,
        org_id: str,
        uploader: User,
        raw_filename: str,
        content_type: str,
        file_bytes: bytes,
        title: Optional[str] = None,
        doc_type: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """
        Validates, securely stores, and records financial document metadata.
        """
        # 1. Strict validation (size, extension, MIME, and magic byte content signatures)
        sanitized_filename, ext, detected_mime, checksum = validate_file_content(
            filename=raw_filename,
            content_type=content_type,
            content=file_bytes,
        )

        doc_id = str(uuid.uuid4())
        # Generate safe, randomized storage key isolated by tenant organization
        storage_key = f"{org_id}/{doc_id}{ext}"

        # 2. Persist to storage outside web root
        saved_path = await self.storage.save_file(storage_key, file_bytes)

        # 3. Create database entity
        final_title = (title or "").strip() or sanitized_filename
        doc = Document(
            id=doc_id,
            title=final_title,
            filename=sanitized_filename,
            storage_key=storage_key,
            file_path=saved_path,
            file_size_bytes=len(file_bytes),
            mime_type=detected_mime,
            file_extension=ext,
            checksum_sha256=checksum,
            status=DocumentStatus.UPLOADED.value,
            doc_type=doc_type.upper() if doc_type else None,
            organization_id=org_id,
            uploader_id=uploader.id if uploader else None,
            extra_metadata=extra_metadata or {},
        )

        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)

        logger.info(
            f"Document ingested successfully: id={doc.id}, org={org_id}, file={sanitized_filename}, size={len(file_bytes)}"
        )
        return doc

    async def list_documents(
        self,
        org_id: str,
        search: Optional[str] = None,
        status: Optional[str] = None,
        doc_type: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedDocumentResponse:
        """
        Queries documents with search, filtering, sorting, and pagination scoped to org.
        """
        items, total = await self.repo.search_and_paginate(
            org_id=org_id,
            search=search,
            status=status,
            doc_type=doc_type,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return PaginatedDocumentResponse(
            items=[DocumentResponse.model_validate(d) for d in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_document(self, doc_id: str, org_id: str) -> Document:
        """Retrieves single document enforcing strict tenant boundary."""
        doc = await self.repo.get_by_id_scoped(doc_id, org_id)
        if not doc:
            raise NotFoundError("Document in this organization", doc_id)
        return doc

    async def get_document_file_for_serving(
        self, doc_id: str, org_id: str
    ) -> Tuple[str, str, str]:
        """
        Retrieves verified safe filesystem path, MIME type, and filename for preview or download.
        Returns: (absolute_file_path, mime_type, filename)
        """
        doc = await self.get_document(doc_id, org_id)

        try:
            safe_path = self.storage.get_absolute_path(doc.storage_key)
        except Exception as e:
            raise ValidationError("Storage path resolution failed", {"detail": str(e)})

        if not self.storage.file_exists(doc.storage_key):
            raise NotFoundError("File binary on storage disk", doc_id)

        return safe_path, doc.mime_type, doc.filename

    async def update_document(
        self, doc_id: str, org_id: str, payload: DocumentUpdate
    ) -> Document:
        """Modifies document metadata or status."""
        doc = await self.get_document(doc_id, org_id)

        if payload.title is not None:
            doc.title = payload.title.strip()
        if payload.doc_type is not None:
            doc.doc_type = payload.doc_type.upper() if payload.doc_type else None
        if payload.status is not None:
            # Validate status
            valid_statuses = [s.value for s in DocumentStatus]
            if payload.status.upper() not in valid_statuses:
                raise ValidationError(
                    f"Invalid status '{payload.status}'. Valid statuses: {valid_statuses}",
                    {"valid_statuses": valid_statuses},
                )
            doc.status = payload.status.upper()
        if payload.extra_metadata is not None:
            doc.extra_metadata = payload.extra_metadata

        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def delete_document(self, doc_id: str, org_id: str) -> str:
        """
        Deletes document metadata from database and purges binary artifact from storage disk.
        """
        doc = await self.get_document(doc_id, org_id)
        doc_title = doc.title
        storage_key = doc.storage_key

        # Delete from disk storage
        try:
            await self.storage.delete_file(storage_key)
        except Exception as err:
            logger.warning(
                f"Error removing file artifact during document deletion: key={storage_key}, error={err}"
            )

        # Delete from database
        await self.db.delete(doc)
        await self.db.commit()

        logger.info(
            f"Document removed successfully: id={doc_id}, org={org_id}, title={doc_title}"
        )
        return doc_title
