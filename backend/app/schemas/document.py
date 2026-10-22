from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentStatusEnum(str, Enum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class UploaderBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str


class DocumentCreate(BaseModel):
    """Payload to register a document under an organization."""
    title: str = Field(..., min_length=1, max_length=255)
    filename: str = Field(..., min_length=1, max_length=255)
    file_size_bytes: int = Field(..., ge=0)
    mime_type: str = "application/pdf"
    doc_type: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None


class DocumentUpdate(BaseModel):
    """Payload to modify document metadata or status."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    doc_type: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    """Public document metadata representation. Internal storage path and storage key are hidden."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: Optional[str]
    title: str
    filename: str
    file_size_bytes: int
    mime_type: str
    file_extension: str
    checksum_sha256: str
    status: str
    doc_type: Optional[str]
    uploader_id: Optional[str] = None
    uploader: Optional[UploaderBrief] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class PaginatedDocumentResponse(BaseModel):
    """Paginated document search and listing response."""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
