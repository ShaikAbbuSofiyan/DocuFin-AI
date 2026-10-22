import enum
import uuid
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base, TimestampMixin


class DocumentStatus(str, enum.Enum):
    """Document processing and review statuses."""
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class Document(Base, TimestampMixin):
    """Financial document entity tracking processing lifecycle and metadata."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    file_extension: Mapped[str] = mapped_column(String(20), default=".pdf")
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    status: Mapped[str] = mapped_column(
        String(50), default=DocumentStatus.UPLOADED.value, index=True
    )
    doc_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )  # 10-K, 10-Q, INVOICE, EARNINGS_CALL, BALANCE_SHEET, OTHER

    # Multi-tenant organization isolation
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Uploader tracking
    uploader_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Use JSON with fallback for non-Postgres environments (e.g. SQLite tests)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )

    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="documents")
    uploader: Mapped[Optional["User"]] = relationship("User")
