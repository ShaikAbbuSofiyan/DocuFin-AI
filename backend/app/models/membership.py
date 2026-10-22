from enum import Enum
import uuid
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class OrganizationRole(str, Enum):
    """Allowed enterprise roles within an organization."""
    ADMIN = "Admin"
    ANALYST = "Analyst"
    REVIEWER = "Reviewer"


class OrganizationMembership(Base, TimestampMixin):
    """Associates users with organizations and defines role-based permissions."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_user_organization_membership"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), default=OrganizationRole.ANALYST.value, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="memberships")
