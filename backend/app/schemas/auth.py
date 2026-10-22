from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Registration payload for new users."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: str = Field(..., min_length=2, max_length=255)
    organization_name: Optional[str] = Field(
        None, max_length=255, description="Initial organization name (optional)"
    )


class UserLoginRequest(BaseModel):
    """Login payload."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Public user profile information."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime


class OrganizationMembershipDetail(BaseModel):
    """Membership information including organization and assigned role."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str
    is_active: bool


class UserMeResponse(BaseModel):
    """Detailed profile response for the authenticated user."""
    user: UserResponse
    memberships: List[OrganizationMembershipDetail]
    active_organization_id: Optional[str] = None
    active_role: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response on successful login or registration."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class MessageResponse(BaseModel):
    """Generic status/message response."""
    message: str
    success: bool = True
