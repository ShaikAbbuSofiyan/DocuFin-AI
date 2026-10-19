import uuid
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON
from app.db.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    """Financial document entity tracking processing lifecycle and metadata."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", index=True
    )  # PENDING, PROCESSING, REVIEW_REQUIRED, COMPLETED, FAILED
    doc_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # 10-K, 10-Q, INVOICE, EARNINGS_CALL, BALANCE_SHEET

    # Use JSON with fallback for non-Postgres environments (e.g. SQLite tests)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
