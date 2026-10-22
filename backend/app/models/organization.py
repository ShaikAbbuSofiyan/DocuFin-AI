import uuid
from typing import List
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Organization(Base, TimestampMixin):
    """Tenant organization entity isolating documents, audits, and member workspaces."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    memberships: Mapped[List["OrganizationMembership"]] = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
