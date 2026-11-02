from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.api.v1.endpoints.documents import get_active_org_membership
from app.models.membership import OrganizationMembership
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.rag import (
    ChatQueryRequest,
    ChatQueryResponse,
    ConversationDetailResponse,
    ConversationResponse,
    IndexDocumentResponse,
)
from app.services.chunking_service import DocumentChunkingService
from app.services.rag_service import FinancialRAGService

router = APIRouter()


@router.post(
    "/chat/query",
    response_model=ChatQueryResponse,
    summary="Submit a financial question with grounded source citations",
)
async def query_financial_assistant(
    request_data: ChatQueryRequest,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a user question to the financial RAG assistant:
    - Enforces organization isolation and document permissions.
    - Deterministically aggregates mathematical totals directly from structured records.
    - Performs hybrid semantic vector and keyword search over document chunks.
    - Returns verifiable source citations (document title, page number, excerpt).
    - Returns an explicit insufficient-information response if evidence is missing.
    """
    service = FinancialRAGService(db=db)
    return await service.query(
        request=request_data,
        organization_id=membership.organization_id,
        user=current_user,
    )


@router.post(
    "/chat/index/{doc_id}",
    response_model=IndexDocumentResponse,
    summary="Chunk and index document text for semantic vector retrieval",
)
async def index_document_for_rag(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """
    Splits document OCR text into overlapping chunks, computes semantic embeddings,
    and stores them in pgvector / database with page number references.
    """
    chunking_service = DocumentChunkingService(db=db)
    chunks = await chunking_service.index_document(
        document_id=doc_id,
        organization_id=membership.organization_id,
    )
    return IndexDocumentResponse(
        document_id=doc_id,
        chunk_count=len(chunks),
        embedding_dimension=chunking_service.embedding_provider.dimension,
        message=f"Successfully indexed {len(chunks)} chunks for document.",
    )


@router.get(
    "/chat/conversations",
    response_model=List[ConversationResponse],
    summary="List active conversation threads for current user",
)
async def list_conversations(
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """Lists user's chat conversations within the active organization."""
    service = FinancialRAGService(db=db)
    return await service.get_conversations(
        organization_id=membership.organization_id,
        user_id=current_user.id,
    )


@router.get(
    "/chat/conversations/{conv_id}",
    response_model=ConversationDetailResponse,
    summary="Get full conversation history and verifiable message citations",
)
async def get_conversation_history(
    conv_id: str,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """Fetches conversation thread with complete message history."""
    service = FinancialRAGService(db=db)
    return await service.get_conversation(
        conversation_id=conv_id,
        organization_id=membership.organization_id,
    )


@router.delete(
    "/chat/conversations/{conv_id}",
    response_model=MessageResponse,
    summary="Delete conversation thread and associated history",
)
async def delete_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_active_user),
    membership: OrganizationMembership = Depends(get_active_org_membership),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a chat conversation thread."""
    service = FinancialRAGService(db=db)
    await service.delete_conversation(
        conversation_id=conv_id,
        organization_id=membership.organization_id,
    )
    return MessageResponse(message="Conversation deleted successfully.")
