import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base, TimestampMixin


class ReviewTaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ReviewTaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReviewTask(Base, TimestampMixin):
    """
    Review task coordinating human analyst verification of extracted financial data,
    validation errors, and state transitions.
    Includes versioning for optimistic concurrency control.
    """

    __tablename__ = "review_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    extraction_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("document_extractions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(30), default=ReviewTaskStatus.PENDING.value, nullable=False, index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), default=ReviewTaskPriority.MEDIUM.value, nullable=False, index=True
    )

    # Assignment & Ownership
    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Concurrency control: monotonic version number checked on updates
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # SLA and deadlines
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Routing reasons & issues
    review_reasons: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list
    )
    validation_error_count: Mapped[int] = mapped_column(Integer, default=0)

    # Reviewer decision details
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship("Document")
    extraction: Mapped[Optional["DocumentExtraction"]] = relationship("DocumentExtraction")
    organization: Mapped["Organization"] = relationship("Organization")
    assigned_to: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to_id])
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_id])
    histories: Mapped[List["ReviewHistory"]] = relationship(
        "ReviewHistory",
        back_populates="review_task",
        cascade="all, delete-orphan",
        order_by="desc(ReviewHistory.created_at)",
    )
