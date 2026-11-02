import uuid
from typing import Any, Dict, Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.config import get_settings
from app.db.base import Base, TimestampMixin

settings = get_settings()


class DocumentChunk(Base, TimestampMixin):
    """
    Stores an individual text chunk from an extracted document page,
    along with its semantic vector embedding and source metadata.
    Enforces multi-tenant organization isolation and page traceability.
    """
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)

    # pgvector embedding column with SQLite JSON fallback for testing
    embedding = mapped_column(
        Vector(settings.embedding_dimension).with_variant(JSON(), "sqlite"),
        nullable=True,
    )

    extra_metadata: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
    )

    # Relationships
    document = relationship("Document", backref="chunks")
    organization = relationship("Organization")
