from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProcessingJobResponse(BaseModel):
    """Metadata response for a document asynchronous processing job."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    organization_id: str
    status: str
    stage: str
    attempts: int
    max_attempts: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class ProcessingJobTriggerRequest(BaseModel):
    """Request payload to initiate or retry a document processing job."""
    force_reprocess: bool = Field(False, description="Whether to reprocess an already completed document")
    idempotency_key: Optional[str] = Field(None, description="Client idempotency token to prevent duplicate queues")


class DocumentPageResponse(BaseModel):
    """Extracted text and OCR telemetry for an individual document page."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    page_number: int
    text_content: str
    word_count: int
    char_count: int
    is_scanned: bool
    has_images: bool
    ocr_applied: bool
    ocr_confidence: Optional[float] = None
    extra_metadata: Optional[Dict[str, Any]] = None


class DocumentExtractedTextResponse(BaseModel):
    """Aggregated textual extraction response preserving page numbers and references."""
    document_id: str
    total_pages: int
    total_words: int
    total_chars: int
    ocr_applied: bool
    pages: List[DocumentPageResponse]
