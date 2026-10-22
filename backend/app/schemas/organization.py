from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganizationCreateRequest(BaseModel):
    """Payload to create a new organization."""
    name: str = Field(..., min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=100)


class OrganizationResponse(BaseModel):
    """Organization metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class AddMemberRequest(BaseModel):
    """Payload to add a user to an organization."""
    email: EmailStr
    role: str = Field("Analyst", description="Role: Admin, Analyst, or Reviewer")


class UpdateMemberRoleRequest(BaseModel):
    """Payload to update an organization member's role."""
    role: str = Field(..., description="Role: Admin, Analyst, or Reviewer")


class OrganizationMemberResponse(BaseModel):
    """Member details in an organization."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
