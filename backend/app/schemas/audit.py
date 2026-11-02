from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditLogItem(BaseModel):
    id: str
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    status: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedAuditLogResponse(BaseModel):
    items: List[AuditLogItem]
    total: int
    page: int
    page_size: int
    total_pages: int
