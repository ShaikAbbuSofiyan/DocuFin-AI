import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin


class ChatConversation(Base, TimestampMixin):
    """
    Maintains a multi-turn RAG chat session scoped to an organization and user.
    Optionally scopes retrieval to a subset of authorized documents.
    """
    __tablename__ = "chat_conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="Financial Assistant Chat")

    # Optional list of document IDs to scope retrieval. Null/empty means all authorized org docs.
    document_ids: Mapped[Optional[list]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True, default=list
    )

    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    user = relationship("User")
    organization = relationship("Organization")


class ChatMessage(Base):
    """
    Individual turn within a financial RAG conversation.
    Records user queries, assistant responses, verifiable source citations,
    and whether the response was derived via deterministic calculation.
    """
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user", "assistant", "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # List of citation objects: [{ document_id, document_title, page_number, excerpt, relevance_score }]
    citations: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )

    # Flag indicating deterministic calculation from structured financial records (no LLM hallucination)
    is_numerical_aggregation: Mapped[bool] = mapped_column(Boolean, default=False)

    token_usage: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationship
    conversation: Mapped["ChatConversation"] = relationship("ChatConversation", back_populates="messages")
