from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AssignReviewTaskRequest(BaseModel):
    assigned_to_id: Optional[str] = Field(None, description="User ID to assign the task to, or null to unassign")


class CorrectFieldsRequest(BaseModel):
    field_updates: Dict[str, Any] = Field(..., description="Map of field names to new values")
    notes: Optional[str] = Field(None, description="Reviewer explanation of corrections made")
    expected_version: int = Field(..., description="Expected current task version for optimistic locking")


class ApproveReviewTaskRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Approval notes or sign-off remarks")
    expected_version: int = Field(..., description="Expected current task version for optimistic locking")


class RejectReviewTaskRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, description="Mandatory reason for rejecting document")
    expected_version: int = Field(..., description="Expected current task version for optimistic locking")


class CreateReviewTaskRequest(BaseModel):
    document_id: str = Field(..., description="Document ID to create review task for")
    priority: Optional[str] = Field("MEDIUM", description="Task priority (LOW, MEDIUM, HIGH, CRITICAL)")
    review_reasons: Optional[List[str]] = Field(default_factory=list, description="Specific triggers for review")


class ReviewTaskQueueItem(BaseModel):
    id: str
    document_id: str
    document_title: str
    document_filename: str
    document_type: Optional[str] = None
    extraction_id: Optional[str] = None
    status: str
    priority: str
    version: int
    assigned_to_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_to_email: Optional[str] = None
    review_reasons: List[str] = Field(default_factory=list)
    validation_error_count: int = 0
    confidence_score: float = 0.0
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PaginatedReviewQueueResponse(BaseModel):
    items: List[ReviewTaskQueueItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReviewHistoryItem(BaseModel):
    id: str
    review_task_id: str
    document_id: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    action: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    field_changes: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewTaskDetailResponse(BaseModel):
    id: str
    document_id: str
    extraction_id: Optional[str] = None
    organization_id: str
    status: str
    priority: str
    assigned_to_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_to_email: Optional[str] = None
    version: int
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    review_reasons: List[str] = Field(default_factory=list)
    validation_error_count: int = 0
    resolution_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    document_title: Optional[str] = None
    document_filename: Optional[str] = None
    document_type: Optional[str] = None
    uploader_id: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    field_metadata: Optional[Dict[str, Any]] = None
    validation_errors: Optional[List[Dict[str, Any]]] = None
    histories: List[ReviewHistoryItem] = Field(default_factory=list)
