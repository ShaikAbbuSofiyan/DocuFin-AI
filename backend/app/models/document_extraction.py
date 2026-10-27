import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base, TimestampMixin


class ExtractionStatus(str, enum.Enum):
    EXTRACTED = "EXTRACTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DocumentExtraction(Base, TimestampMixin):
    """
    Stores structured financial entities extracted from document OCR text.
    Maintains schema versioning, per-field confidence, and human review states.
    """

    __tablename__ = "document_extractions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="UNKNOWN", index=True
    )
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    schema_version: Mapped[str] = mapped_column(String(20), default="v1.0")

    # Structured financial data (JSON representation of InvoiceData, BankStatementData, etc.)
    extracted_data: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
    )

    # Per-field metadata: { field_name: { value, raw_value, source_page, extraction_method, confidence } }
    field_metadata: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
    )

    extraction_method: Mapped[str] = mapped_column(
        String(50), default="LLM"
    )  # LLM, DETERMINISTIC_FALLBACK, HYBRID, MANUAL
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    token_usage: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )

    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)

    # Human-in-the-loop review routing
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    review_reasons: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_errors: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list
    )

    status: Mapped[str] = mapped_column(
        String(50), default=ExtractionStatus.EXTRACTED.value, index=True
    )

    reviewed_by_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    analyst_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extractions")
    reviewed_by: Mapped[Optional["User"]] = relationship("User")
