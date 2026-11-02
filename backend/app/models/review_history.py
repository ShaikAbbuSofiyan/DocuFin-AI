import uuid
from typing import Optional
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base, TimestampMixin


class ReviewHistory(Base, TimestampMixin):
    """
    Chronological historical audit records of all reviewer decisions,
    field corrections (storing before and after values), assignments, and notes.
    """

    __tablename__ = "review_histories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # CREATED, ASSIGNED, FIELD_CORRECTION, APPROVED, REJECTED, STATUS_CHANGE

    previous_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Detailed field changes: { "total_amount": { "old_value": 1200.0, "new_value": 1500.0 } }
    field_changes: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    review_task: Mapped["ReviewTask"] = relationship("ReviewTask", back_populates="histories")
    user: Mapped[Optional["User"]] = relationship("User")
    document: Mapped["Document"] = relationship("Document")
