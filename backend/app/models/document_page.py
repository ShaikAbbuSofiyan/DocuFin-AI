import uuid
from typing import Optional
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base, TimestampMixin


class DocumentPage(Base, TimestampMixin):
    """
    Stores extracted textual content and per-page OCR/digital metadata preserving page references.
    """

    __tablename__ = "document_pages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_scanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_images: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )

    document: Mapped["Document"] = relationship("Document", back_populates="pages")
