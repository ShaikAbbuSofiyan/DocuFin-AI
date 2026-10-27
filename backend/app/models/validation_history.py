import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base, TimestampMixin


class ValidationSeverity(str, enum.Enum):
    """Severity tier for financial business rule evaluations."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationRun(Base, TimestampMixin):
    """
    Stores an immutable historical record of financial business rule validation execution.
    Preserves auditability of automated rule checks across manual edits and system updates.
    """
    __tablename__ = "validation_runs"

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

    triggered_by: Mapped[str] = mapped_column(
        String(50), default="EXTRACTION"  # EXTRACTION, MANUAL_CORRECTION, API_REVALIDATE
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    info_count: Mapped[int] = mapped_column(Integer, default=0)

    # List of rule result dictionaries:
    # [{ rule_id, rule_name, severity, is_passed, explanation, affected_fields }]
    results: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", backref="validation_runs")
    extraction: Mapped[Optional["DocumentExtraction"]] = relationship("DocumentExtraction", backref="validation_runs")
