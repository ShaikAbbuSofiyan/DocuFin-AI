from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class QueryType(str, Enum):
    """Categorization of RAG answer generation method."""
    DETERMINISTIC_AGGREGATION = "DETERMINISTIC_AGGREGATION"
    RETRIEVAL_AUGMENTED_GENERATION = "RETRIEVAL_AUGMENTED_GENERATION"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class CitationItem(BaseModel):
    """Verifiable reference pointing back to source document page and excerpt."""
    document_id: str
    document_title: str
    page_number: int
    excerpt: str
    relevance_score: float = Field(1.0, ge=0.0, le=1.0)


class ChatQueryRequest(BaseModel):
    """Payload for submitting a financial question."""
    query: str = Field(..., min_length=2, max_length=2000, description="User question or financial request")
    conversation_id: Optional[str] = Field(None, description="Active conversation thread ID")
    document_ids: Optional[List[str]] = Field(default=None, description="Optional list of document IDs to scope retrieval")
    use_hybrid: bool = Field(True, description="Enable hybrid semantic + keyword scoring")


class ChatQueryResponse(BaseModel):
    """Complete grounded answer response with verifiable source citations."""
    conversation_id: str
    message_id: str
    answer: str
    citations: List[CitationItem] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    is_numerical_aggregation: bool = False
    query_type: QueryType = QueryType.RETRIEVAL_AUGMENTED_GENERATION


class ChatMessageResponse(BaseModel):
    """Message item within a conversation thread."""
    id: str
    conversation_id: str
    role: str
    content: str
    citations: List[CitationItem] = Field(default_factory=list)
    is_numerical_aggregation: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """Overview summary of a chat conversation."""
    id: str
    organization_id: str
    user_id: str
    title: str
    document_ids: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(ConversationResponse):
    """Full conversation with message history."""
    messages: List[ChatMessageResponse] = Field(default_factory=list)


class IndexDocumentResponse(BaseModel):
    """Result of document chunking and vector indexing."""
    document_id: str
    chunk_count: int
    embedding_dimension: int
    message: str
