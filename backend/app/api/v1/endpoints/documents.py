import os
import uuid
from typing import Any, List, Optional, Tuple, Union
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import (
    get_current_active_user,
    require_organization_membership,
    require_role,
)
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.membership import OrganizationMembership, OrganizationRole
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    PaginatedDocumentResponse,
)
from app.schemas.processing import (
    DocumentExtractedTextResponse,
    ProcessingJobResponse,
    ProcessingJobTriggerRequest,
)
from app.schemas.extraction import (
    ClassificationResult,
    DocumentExtractionResponse,
    DocumentExtractionUpdate,
    ReviewQueueItem,
    TriggerExtractionRequest,
)
from app.schemas.validation import (
    TriggerValidationRequest,
    ValidationRunResponse,
    ValidationSummary,
)
from app.services.document_service import DocumentService
from app.services.extraction_service import FinancialExtractionService
from app.workers.document_tasks import recover_stale_jobs

router = APIRouter()


async def get_active_org_membership(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMembership:
    """Resolves the user's active organization membership from header or active memberships."""
    active_org_id = request.headers.get("X-Organization-Id")
    if active_org_id:
        for m in current_user.memberships:
            if m.is_active and m.organization_id == active_org_id:
                return m

    # Fallback to first active membership
    for m in current_user.memberships:
        if m.is_active:
            return m

    if current_user.is_superuser:
        # Superuser fallback if no membership
        first_org_res = await db.execute(select(Document.organization_id).limit(1))
        first_org = first_org_res.scalar_one_or_none() or "system"
        return OrganizationMembership(
            id="superuser-active",
            user_id=current_user.id,
            organization_id=first_org,
            role=OrganizationRole.ADMIN.value,
            is_active=True,
            user=current_user,
        )

    raise ForbiddenError("No active organization membership found. Please join or create an organization.")


async def verify_document_access(
    doc_id: str,
    current_user: User,
    db: AsyncSession,
) -> Tuple[Document, Optional[OrganizationMembership]]:
    """Verifies that the user has an active membership in the document's organization."""
    query = (
        select(Document)
        .where(Document.id == doc_id)
        .options(selectinload(Document.uploader))
    )
    res = await db.execute(query)
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document", doc_id)

    # Check user membership
    user_mem = next(
        (m for m in current_user.memberships if m.is_active and m.organization_id == doc.organization_id),
        None,
    )
    if not user_mem and not current_user.is_superuser:
        raise ForbiddenError("You do not have access to this document's organization.")

    return doc, user_mem


# ==============================================================================
# Document Upload Endpoints
# ==============================================================================

@router.post(
    "/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document (PDF, PNG, JPEG) with validation to active organization",
)
async def upload_document_active_org(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingests and validates document file (PDF, PNG, JPEG) up to 50MB.
    Checks size, MIME type, extension, and binary magic bytes.
    Enforces Admin or Analyst role in the active organization.
    """
    if membership.role.lower() not in [
        OrganizationRole.ADMIN.value.lower(),
        OrganizationRole.ANALYST.value.lower(),
    ]:
        raise ForbiddenError("Only Administrators and Analysts can upload documents.")

    content = await file.read()
    service = DocumentService(db)
    doc = await service.upload_document(
        org_id=membership.organization_id,
        uploader=current_user,
        raw_filename=file.filename or "upload.pdf",
        content_type=file.content_type or "application/octet-stream",
        file_bytes=content,
        title=title,
        doc_type=doc_type,
    )
    return doc


@router.post(
    "/organizations/{org_id}/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document to a specific organization with validation",
)
async def upload_document_specific_org(
    org_id: str,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    membership: OrganizationMembership = Depends(
        require_role([OrganizationRole.ADMIN.value, OrganizationRole.ANALYST.value], "org_id")
    ),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Uploads and validates a document into the specified organization."""
    content = await file.read()
    service = DocumentService(db)
    doc = await service.upload_document(
        org_id=org_id,
        uploader=current_user,
        raw_filename=file.filename or "upload.pdf",
        content_type=file.content_type or "application/octet-stream",
        file_bytes=content,
        title=title,
        doc_type=doc_type,
    )
    return doc


@router.post(
    "/organizations/{org_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document entry under an organization (JSON metadata)",
)
async def create_org_document_legacy(
    org_id: str,
    payload: DocumentCreate,
    membership: OrganizationMembership = Depends(
        require_role([OrganizationRole.ADMIN.value, OrganizationRole.ANALYST.value], "org_id")
    ),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Registers document metadata isolated to this organization."""
    service = DocumentService(db)
    # Check extension
    _, ext = os.path.splitext(payload.filename.lower())
    if not ext:
        ext = ".pdf"
    storage_key = f"{org_id}/{uuid.uuid4()}{ext}"

    doc = Document(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        uploader_id=current_user.id,
        title=payload.title,
        filename=payload.filename,
        storage_key=storage_key,
        file_path=f"./storage/documents/{storage_key}",
        file_size_bytes=payload.file_size_bytes,
        mime_type=payload.mime_type,
        file_extension=ext,
        checksum_sha256="",
        status=DocumentStatus.UPLOADED.value,
        doc_type=payload.doc_type,
        extra_metadata=payload.extra_metadata or {},
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# ==============================================================================
# Document Query, Search, Filter & Pagination Endpoints
# ==============================================================================

@router.get(
    "/documents",
    response_model=PaginatedDocumentResponse,
    summary="List documents for user's active organization with search, filter, and pagination",
)
async def list_documents_active_org(
    search: Optional[str] = Query(None, description="Search term for title or filename"),
    status: Optional[str] = Query(None, description="Filter by DocumentStatus"),
    doc_type: Optional[str] = Query(None, description="Filter by doc_type (e.g. 10-K, INVOICE)"),
    sort_by: str = Query("created_at", description="Sort field: created_at, title, file_size_bytes"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """Returns paginated, searchable, and filterable documents for user's active organization."""
    service = DocumentService(db)
    return await service.list_documents(
        org_id=membership.organization_id,
        search=search,
        status=status,
        doc_type=doc_type,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/organizations/{org_id}/documents",
    response_model=Union[PaginatedDocumentResponse, List[DocumentResponse]],
    summary="List documents for an organization (Strict isolation)",
)
async def list_org_documents(
    org_id: str,
    paginate: bool = Query(False, description="Return full paginated schema if true"),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    membership: OrganizationMembership = Depends(require_organization_membership("org_id")),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns documents belonging strictly to the specified organization.
    Supports either plain list or full pagination.
    """
    service = DocumentService(db)
    paginated_res = await service.list_documents(
        org_id=org_id,
        search=search,
        status=status,
        doc_type=doc_type,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    if paginate:
        return paginated_res
    return paginated_res.items


# ==============================================================================
# Single Document Retrieval, Details, Preview & Download Endpoints
# ==============================================================================

@router.get(
    "/documents/review-queue",
    response_model=List[ReviewQueueItem],
    summary="List documents routed to manual human-in-the-loop review",
)
async def get_review_queue_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves confidence-ranked items requiring human analyst sign-off
    due to low confidence, mathematical ledger discrepancies, or missing critical fields.
    """
    service = FinancialExtractionService(db)
    items, _ = await service.get_review_queue(
        org_id=membership.organization_id,
        page=page,
        page_size=page_size,
    )
    return items


@router.get(
    "/documents/{doc_id}",
    response_model=DocumentResponse,
    summary="Get document details by ID with organization verification",
)
async def get_document_by_id(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetches document details if user belongs to the document's organization."""
    doc, _ = await verify_document_access(doc_id, current_user, db)
    return doc


@router.get(
    "/organizations/{org_id}/documents/{doc_id}",
    response_model=DocumentResponse,
    summary="Get single document with organization isolation verification",
)
async def get_org_document_legacy(
    org_id: str,
    doc_id: str,
    membership: OrganizationMembership = Depends(require_organization_membership("org_id")),
    db: AsyncSession = Depends(get_db),
):
    """Fetches a document ensuring it belongs strictly to this organization."""
    service = DocumentService(db)
    return await service.get_document(doc_id, org_id)


@router.get(
    "/documents/{doc_id}/preview",
    summary="Safe inline preview for PDF, PNG, or JPEG documents",
)
async def preview_document(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Serves document file with Content-Disposition inline for safe browser previewing.
    Prevents path traversal and validates tenant boundary.
    """
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = DocumentService(db)
    safe_path, mime_type, filename = await service.get_document_file_for_serving(
        doc_id=doc.id, org_id=doc.organization_id
    )

    return FileResponse(
        path=safe_path,
        media_type=mime_type,
        filename=filename,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get(
    "/organizations/{org_id}/documents/{doc_id}/preview",
    summary="Safe inline preview for PDF, PNG, or JPEG documents (Org-scoped)",
)
async def preview_org_document(
    org_id: str,
    doc_id: str,
    membership: OrganizationMembership = Depends(require_organization_membership("org_id")),
    db: AsyncSession = Depends(get_db),
):
    """Serves document for preview within organization scope."""
    service = DocumentService(db)
    safe_path, mime_type, filename = await service.get_document_file_for_serving(
        doc_id=doc_id, org_id=org_id
    )
    return FileResponse(
        path=safe_path,
        media_type=mime_type,
        filename=filename,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get(
    "/documents/{doc_id}/download",
    summary="Safe attachment download for documents",
)
async def download_document(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Serves document file with Content-Disposition attachment for downloading.
    Prevents path traversal and validates tenant boundary.
    """
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = DocumentService(db)
    safe_path, mime_type, filename = await service.get_document_file_for_serving(
        doc_id=doc.id, org_id=doc.organization_id
    )

    return FileResponse(
        path=safe_path,
        media_type=mime_type,
        filename=filename,
        content_disposition_type="attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/organizations/{org_id}/documents/{doc_id}/download",
    summary="Safe attachment download for documents (Org-scoped)",
)
async def download_org_document(
    org_id: str,
    doc_id: str,
    membership: OrganizationMembership = Depends(require_organization_membership("org_id")),
    db: AsyncSession = Depends(get_db),
):
    """Serves document for attachment download within organization scope."""
    service = DocumentService(db)
    safe_path, mime_type, filename = await service.get_document_file_for_serving(
        doc_id=doc_id, org_id=org_id
    )
    return FileResponse(
        path=safe_path,
        media_type=mime_type,
        filename=filename,
        content_disposition_type="attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
        },
    )


# ==============================================================================
# Document Update and Deletion Endpoints
# ==============================================================================

@router.patch(
    "/documents/{doc_id}",
    response_model=DocumentResponse,
    summary="Update document metadata or processing status",
)
async def update_document_endpoint(
    doc_id: str,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Updates document metadata or status with organization authorization check."""
    doc, mem = await verify_document_access(doc_id, current_user, db)
    if mem and mem.role.lower() not in [
        OrganizationRole.ADMIN.value.lower(),
        OrganizationRole.ANALYST.value.lower(),
    ]:
        raise ForbiddenError("Reviewers cannot edit document metadata.")

    service = DocumentService(db)
    return await service.update_document(doc_id=doc.id, org_id=doc.organization_id, payload=payload)


@router.delete(
    "/documents/{doc_id}",
    response_model=MessageResponse,
    summary="Delete document from database and purge from storage",
)
async def delete_document_endpoint(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes document record and cleans up filesystem storage artifact.
    Requires Admin privileges in the organization.
    """
    doc, mem = await verify_document_access(doc_id, current_user, db)
    if mem and mem.role.lower() != OrganizationRole.ADMIN.value.lower() and not current_user.is_superuser:
        raise ForbiddenError("Only Administrators can delete documents.")

    service = DocumentService(db)
    title = await service.delete_document(doc_id=doc.id, org_id=doc.organization_id)
    return MessageResponse(message=f"Document '{title}' deleted successfully.")


@router.delete(
    "/organizations/{org_id}/documents/{doc_id}",
    response_model=MessageResponse,
    summary="Delete a document from an organization (Admin role required)",
)
async def delete_org_document_legacy(
    org_id: str,
    doc_id: str,
    membership: OrganizationMembership = Depends(
        require_role([OrganizationRole.ADMIN.value], "org_id")
    ),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a document from the organization. Requires Admin privileges."""
    service = DocumentService(db)
    title = await service.delete_document(doc_id=doc_id, org_id=org_id)
    return MessageResponse(message=f"Document '{title}' deleted successfully.")


# ==============================================================================
# Phase 4: Asynchronous Processing & OCR Endpoints
# ==============================================================================

@router.post(
    "/documents/{doc_id}/process",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue asynchronous text extraction and OCR job",
)
async def process_document_endpoint(
    doc_id: str,
    payload: Optional[ProcessingJobTriggerRequest] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits an uploaded document to Celery background worker for PDF digital text
    extraction and Tesseract OCR on scanned pages.
    Guarantees bounded retries, distributed deduplication, and idempotency.
    Requires Admin or Analyst role in the document's organization.
    """
    doc, mem = await verify_document_access(doc_id, current_user, db)
    if mem and mem.role.lower() not in [
        OrganizationRole.ADMIN.value.lower(),
        OrganizationRole.ANALYST.value.lower(),
    ] and not current_user.is_superuser:
        raise ForbiddenError("Only Administrators and Analysts can trigger document processing.")

    service = DocumentService(db)
    force = payload.force_reprocess if payload else False
    idempotency_key = payload.idempotency_key if payload else None

    job = await service.queue_document_processing(
        doc_id=doc.id,
        org_id=doc.organization_id,
        force_reprocess=force,
        idempotency_key=idempotency_key,
    )
    return job


@router.get(
    "/documents/{doc_id}/processing-jobs",
    response_model=List[ProcessingJobResponse],
    summary="List all processing jobs for a document",
)
async def list_document_processing_jobs(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists processing job history with timestamps, attempts, durations, and errors."""
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = DocumentService(db)
    jobs = await service.get_processing_jobs(doc_id=doc.id, org_id=doc.organization_id)
    return jobs


@router.get(
    "/documents/{doc_id}/processing-jobs/{job_id}",
    response_model=ProcessingJobResponse,
    summary="Poll status of a specific document processing job",
)
async def get_document_processing_job_status(
    doc_id: str,
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint for frontend status polling.
    Returns status (PENDING, PROCESSING, RETRYING, COMPLETED, FAILED),
    stage progress, attempt count, duration in ms, and any error message.
    """
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = DocumentService(db)
    job = await service.get_processing_job(
        doc_id=doc.id, job_id=job_id, org_id=doc.organization_id
    )
    return job


@router.post(
    "/documents/{doc_id}/retry",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Failed-job recovery: Re-queue processing for a failed document",
)
async def retry_document_processing(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Forces re-queueing of a failed or stuck document processing job."""
    doc, mem = await verify_document_access(doc_id, current_user, db)
    if mem and mem.role.lower() not in [
        OrganizationRole.ADMIN.value.lower(),
        OrganizationRole.ANALYST.value.lower(),
    ] and not current_user.is_superuser:
        raise ForbiddenError("Only Administrators and Analysts can retry document processing.")

    service = DocumentService(db)
    job = await service.queue_document_processing(
        doc_id=doc.id,
        org_id=doc.organization_id,
        force_reprocess=True,
    )
    return job


@router.get(
    "/documents/{doc_id}/extracted-text",
    response_model=DocumentExtractedTextResponse,
    summary="Retrieve extracted text and OCR data preserving page numbers",
)
async def get_document_extracted_text(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves complete page-by-page extracted text, word counts, char counts,
    and OCR indicators for verification and downstream financial research.
    """
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = DocumentService(db)
    extracted = await service.get_extracted_pages(doc_id=doc.id, org_id=doc.organization_id)
    return extracted


@router.post(
    "/documents/recover-stale-jobs",
    response_model=MessageResponse,
    summary="Trigger failed-job recovery mechanism for stale worker jobs",
)
async def recover_stale_jobs_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Failed-job recovery mechanism:
    Scans for jobs stuck in PROCESSING longer than threshold (e.g. following worker crash or reboot)
    and resets them to FAILED so they can be gracefully retried.
    """
    if not current_user.is_superuser:
        # Check if user is admin in any org
        has_admin = any(
            m.is_active and m.role.lower() == OrganizationRole.ADMIN.value.lower()
            for m in current_user.memberships
        )
        if not has_admin:
            raise ForbiddenError("Administrator privileges required to invoke job recovery.")

    count = await recover_stale_jobs(db_session=db)
    return MessageResponse(message=f"Recovery scan completed. {count} stale jobs updated.")


# ==============================================================================
# Phase 5: Financial Document Intelligence & Structured Extraction Endpoints
# ==============================================================================

@router.post(
    "/documents/{doc_id}/extract",
    response_model=DocumentExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract structured financial entities from document OCR text",
)
async def extract_document_endpoint(
    doc_id: str,
    payload: Optional[TriggerExtractionRequest] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes financial document intelligence using versioned Pydantic schemas.
    Applies LLM extraction, deterministic fallback, math verification, and review routing.
    Independent of specific LLM providers.
    """
    doc, mem = await verify_document_access(doc_id, current_user, db)
    if mem and mem.role.lower() not in [
        OrganizationRole.ADMIN.value.lower(),
        OrganizationRole.ANALYST.value.lower(),
    ] and not current_user.is_superuser:
        raise ForbiddenError("Only Administrators and Analysts can trigger structured extraction.")

    pref_type = payload.document_type if payload else None
    force = payload.force_reextract if payload else False

    service = FinancialExtractionService(db)
    extraction = await service.extract_document(
        doc_id=doc.id,
        org_id=doc.organization_id,
        preferred_doc_type=pref_type,
        force_reextract=force,
    )
    return extraction


@router.get(
    "/documents/{doc_id}/extraction",
    response_model=DocumentExtractionResponse,
    summary="Inspect latest structured extraction, field-level confidence and source page references",
)
async def get_document_extraction_endpoint(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns extracted structured financial data, per-field source page references,
    confidence indicators, and review audit history.
    """
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = FinancialExtractionService(db)
    extraction = await service.get_extraction(doc_id=doc.id, org_id=doc.organization_id)
    if not extraction:
        raise NotFoundError("Structured extraction for document", doc_id)
    return extraction


@router.patch(
    "/documents/{doc_id}/extraction",
    response_model=DocumentExtractionResponse,
    summary="Update or correct extracted financial fields and submit review decision",
)
async def update_document_extraction_endpoint(
    doc_id: str,
    payload: DocumentExtractionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Allows analysts and reviewers to edit extracted fields in the UI,
    record audit notes, and mark documents as APPROVED or REJECTED.
    """
    doc, mem = await verify_document_access(doc_id, current_user, db)
    service = FinancialExtractionService(db)
    updated = await service.update_extraction(
        doc_id=doc.id,
        org_id=doc.organization_id,
        payload=payload,
        analyst_user=current_user,
    )
    return updated


@router.post(
    "/documents/{doc_id}/classify",
    response_model=ClassificationResult,
    summary="Classify document category (Invoice, Bank Statement, Expense Report)",
)
async def classify_document_endpoint(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Classifies document using domain heuristics and keyword density scoring."""
    doc, _ = await verify_document_access(doc_id, current_user, db)
    doc_service = DocumentService(db)
    pages = await doc_service.get_extracted_pages(doc_id=doc.id, org_id=doc.organization_id)
    if not pages.pages:
        raise ValidationError("Document has no OCR pages. Run processing first.")

    full_text = "\n".join(p.text_content for p in pages.pages)
    service = FinancialExtractionService(db)
    return await service.llm_provider.classify_document(full_text)


# ==============================================================================
# Financial Business Rules & Validation Engine Endpoints (Phase 6)
# ==============================================================================

@router.post(
    "/documents/{doc_id}/validate",
    response_model=ValidationSummary,
    summary="Trigger on-demand deterministic business rule validation",
)
async def validate_document_endpoint(
    doc_id: str,
    payload: Optional[TriggerValidationRequest] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes high-precision decimal arithmetic checks, mandatory field validations,
    ledger reconciliations, duplicate detection, and records an immutable historical run.
    """
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = FinancialExtractionService(db)
    tol = payload.rounding_tolerance if payload else None
    strict = payload.strict_mode if payload else None
    summary, _ = await service.revalidate_extraction(
        doc_id=doc.id,
        org_id=doc.organization_id,
        rounding_tolerance=tol,
        strict_mode=strict,
    )
    return summary


@router.get(
    "/documents/{doc_id}/validation-latest",
    response_model=ValidationRunResponse,
    summary="Get the most recent validation run results and rule details",
)
async def get_latest_validation_endpoint(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves the latest validation run for the document."""
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = FinancialExtractionService(db)
    val_run = await service.get_latest_validation(doc_id=doc.id, org_id=doc.organization_id)
    if not val_run:
        raise NotFoundError("ValidationRun for document", doc_id)
    return val_run


@router.get(
    "/documents/{doc_id}/validation-history",
    response_model=List[ValidationRunResponse],
    summary="Get chronological history of all validation runs for a document",
)
async def get_validation_history_endpoint(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns chronological audit trail of all automated and manual validation runs."""
    doc, _ = await verify_document_access(doc_id, current_user, db)
    service = FinancialExtractionService(db)
    return await service.get_validation_history(doc_id=doc.id, org_id=doc.organization_id)
