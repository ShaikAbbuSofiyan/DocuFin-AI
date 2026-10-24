import math
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundError, ValidationError
from app.core.file_validation import validate_file_content
from app.core.logging import logger
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.processing_job import JobStatus, ProcessingJob, ProcessingStage
from app.models.user import User
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import (
    DocumentResponse,
    DocumentUpdate,
    PaginatedDocumentResponse,
)
from app.schemas.processing import (
    DocumentExtractedTextResponse,
    DocumentPageResponse,
    ProcessingJobResponse,
)
from app.services.storage import get_storage_service
from app.services.storage.base import StorageService
from app.workers.document_tasks import process_document_task


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

    async def queue_document_processing(
        self,
        doc_id: str,
        org_id: str,
        force_reprocess: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> ProcessingJob:
        """
        Submits an authorized document for asynchronous text extraction and OCR.
        Enforces idempotency, tenant boundaries, and deduplication.
        """
        doc = await self.get_document(doc_id, org_id)

        # 1. Idempotency Key check: if specified, check for existing job with same key
        if idempotency_key:
            stmt = select(ProcessingJob).where(
                ProcessingJob.idempotency_key == idempotency_key,
                ProcessingJob.organization_id == org_id,
            )
            res = await self.db.execute(stmt)
            existing_key_job = res.scalar_one_or_none()
            if existing_key_job:
                logger.info(
                    f"Idempotent processing match for key={idempotency_key}, job_id={existing_key_job.id}"
                )
                return existing_key_job

        # 2. Check for active (PENDING/PROCESSING/RETRYING) jobs
        active_stmt = select(ProcessingJob).where(
            ProcessingJob.document_id == doc_id,
            ProcessingJob.organization_id == org_id,
            ProcessingJob.status.in_([
                JobStatus.PENDING.value,
                JobStatus.PROCESSING.value,
                JobStatus.RETRYING.value,
            ]),
        ).order_by(ProcessingJob.created_at.desc())
        active_res = await self.db.execute(active_stmt)
        active_job = active_res.scalar_one_or_none()

        if active_job and not force_reprocess:
            logger.info(f"Returning active processing job {active_job.id} for document {doc_id}")
            return active_job

        # 3. Check if document is already completed and force_reprocess is False
        if not force_reprocess and doc.status in (DocumentStatus.REVIEW_REQUIRED.value, DocumentStatus.APPROVED.value):
            completed_stmt = select(ProcessingJob).where(
                ProcessingJob.document_id == doc_id,
                ProcessingJob.organization_id == org_id,
                ProcessingJob.status == JobStatus.COMPLETED.value,
            ).order_by(ProcessingJob.created_at.desc())
            completed_res = await self.db.execute(completed_stmt)
            completed_job = completed_res.scalar_one_or_none()
            if completed_job:
                return completed_job

        # 4. Create new ProcessingJob entity
        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            document_id=doc.id,
            organization_id=org_id,
            status=JobStatus.PENDING.value,
            stage=ProcessingStage.QUEUED.value,
            attempts=0,
            max_attempts=3,
            idempotency_key=idempotency_key,
            extra_metadata={"queued_by": "api"},
        )
        self.db.add(job)
        doc.status = DocumentStatus.QUEUED.value
        await self.db.commit()
        await self.db.refresh(job)

        # 5. Dispatch Celery task
        try:
            task = process_document_task.delay(job_id=job.id, document_id=doc.id)
            job.celery_task_id = task.id
            await self.db.commit()
            await self.db.refresh(job)
        except Exception as queue_err:
            logger.warning(
                f"Celery broker dispatch failed (worker might be offline or in local test mode): {str(queue_err)}"
            )

        logger.info(f"Document processing queued: job_id={job.id}, doc_id={doc.id}")
        return job

    async def get_processing_jobs(
        self, doc_id: str, org_id: str
    ) -> List[ProcessingJob]:
        """Queries all processing jobs for a document in org."""
        await self.get_document(doc_id, org_id)
        stmt = (
            select(ProcessingJob)
            .where(
                ProcessingJob.document_id == doc_id,
                ProcessingJob.organization_id == org_id,
            )
            .order_by(ProcessingJob.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_processing_job(
        self, doc_id: str, job_id: str, org_id: str
    ) -> ProcessingJob:
        """Retrieves a single processing job with strict tenant scoping."""
        await self.get_document(doc_id, org_id)
        stmt = select(ProcessingJob).where(
            ProcessingJob.id == job_id,
            ProcessingJob.document_id == doc_id,
            ProcessingJob.organization_id == org_id,
        )
        res = await self.db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise NotFoundError("Processing Job", job_id)
        return job

    async def get_extracted_pages(
        self, doc_id: str, org_id: str
    ) -> DocumentExtractedTextResponse:
        """Retrieves structured, page-ordered text extractions and OCR indicators."""
        doc = await self.get_document(doc_id, org_id)
        stmt = (
            select(DocumentPage)
            .where(DocumentPage.document_id == doc_id)
            .order_by(DocumentPage.page_number.asc())
        )
        res = await self.db.execute(stmt)
        pages = list(res.scalars().all())

        page_responses = [DocumentPageResponse.model_validate(p) for p in pages]
        total_words = sum(p.word_count for p in page_responses)
        total_chars = sum(p.char_count for p in page_responses)
        ocr_applied = any(p.ocr_applied for p in page_responses)

        return DocumentExtractedTextResponse(
            document_id=doc_id,
            total_pages=len(page_responses),
            total_words=total_words,
            total_chars=total_chars,
            ocr_applied=ocr_applied,
            pages=page_responses,
        )
