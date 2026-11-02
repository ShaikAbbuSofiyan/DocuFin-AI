import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage

logger = logging.getLogger("docufin.services.chunking_service")


class DocumentChunkingService:
    """
    Chunks extracted document text preserving page numbers, document IDs,
    organization IDs, and access metadata, then computes and persists vector embeddings.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: Optional[EmbeddingProvider] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.embedding_provider = embedding_provider or get_embedding_provider(self.settings)
        self.chunk_size = chunk_size or self.settings.rag_chunk_size
        self.chunk_overlap = chunk_overlap or self.settings.rag_chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        """
        Splits text into overlapping chunks, respecting paragraph and sentence boundaries.
        Guarantees non-empty, clean chunks.
        """
        if not text or not text.strip():
            return []

        clean = text.strip()
        if len(clean) <= self.chunk_size:
            return [clean]

        chunks = []
        # Split on double newlines (paragraphs) or sentences
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean) if p.strip()]

        current_chunk = ""
        for p in paragraphs:
            # If paragraph itself is larger than chunk_size, split by sentences
            if len(p) > self.chunk_size:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]
                for s in sentences:
                    if len(current_chunk) + len(s) + 1 <= self.chunk_size:
                        current_chunk = f"{current_chunk} {s}".strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                            # Overlap from end of current chunk
                            overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else ""
                            current_chunk = f"{overlap_text} {s}".strip()
                        else:
                            # Single sentence exceeds chunk size, split hard by characters
                            for i in range(0, len(s), self.chunk_size - self.chunk_overlap):
                                sub = s[i : i + self.chunk_size]
                                if sub.strip():
                                    chunks.append(sub.strip())
                            current_chunk = ""
            else:
                if len(current_chunk) + len(p) + 2 <= self.chunk_size:
                    current_chunk = f"{current_chunk}\n\n{p}".strip()
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else ""
                        current_chunk = f"{overlap_text}\n\n{p}".strip()
                    else:
                        current_chunk = p

        if current_chunk and current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    async def index_document(
        self,
        document_id: str,
        organization_id: str,
    ) -> List[DocumentChunk]:
        """
        Extracts pages from document OCR, chunks text, generates embeddings,
        and saves DocumentChunk records in PostgreSQL/SQLite.
        """
        # 1. Fetch document and verify tenant isolation
        doc_query = select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
        res = await self.db.execute(doc_query)
        doc = res.scalar_one_or_none()
        if not doc:
            raise NotFoundError("Document", document_id)

        # 2. Fetch extracted pages
        pages_query = (
            select(DocumentPage)
            .where(
                DocumentPage.document_id == document_id,
            )
            .order_by(DocumentPage.page_number)
        )
        pages_res = await self.db.execute(pages_query)
        pages = list(pages_res.scalars().all())

        raw_chunks: List[Dict[str, Any]] = []

        if pages:
            chunk_global_idx = 0
            for page in pages:
                page_text = page.text_content or ""
                page_chunks = self.chunk_text(page_text)
                for chunk_text in page_chunks:
                    approx_tokens = max(1, len(chunk_text.split()))
                    raw_chunks.append({
                        "document_id": document_id,
                        "organization_id": organization_id,
                        "page_number": page.page_number,
                        "chunk_index": chunk_global_idx,
                        "content": chunk_text,
                        "token_count": approx_tokens,
                        "metadata": {
                            "document_title": doc.title or doc.filename,
                            "filename": doc.filename,
                            "page_number": page.page_number,
                            "doc_type": doc.doc_type,
                        },
                    })
                    chunk_global_idx += 1
        else:
            # Fallback if pages not stored yet: use document title / metadata
            fallback_text = f"Document: {doc.title or doc.filename}. Type: {doc.doc_type or 'Unknown'}."
            raw_chunks.append({
                "document_id": document_id,
                "organization_id": organization_id,
                "page_number": 1,
                "chunk_index": 0,
                "content": fallback_text,
                "token_count": len(fallback_text.split()),
                "metadata": {
                    "document_title": doc.title or doc.filename,
                    "filename": doc.filename,
                    "page_number": 1,
                    "doc_type": doc.doc_type,
                },
            })

        if not raw_chunks:
            return []

        # 3. Generate embeddings in batch
        texts_to_embed = [c["content"] for c in raw_chunks]
        embeddings = await self.embedding_provider.embed_texts(texts_to_embed)

        # 4. Remove previous chunks for idempotent re-indexing
        del_stmt = delete(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.organization_id == organization_id,
        )
        await self.db.execute(del_stmt)

        # 5. Persist DocumentChunk entities
        chunk_models: List[DocumentChunk] = []
        for i, c_data in enumerate(raw_chunks):
            emb = embeddings[i] if i < len(embeddings) else None
            chunk = DocumentChunk(
                document_id=c_data["document_id"],
                organization_id=c_data["organization_id"],
                page_number=c_data["page_number"],
                chunk_index=c_data["chunk_index"],
                content=c_data["content"],
                token_count=c_data["token_count"],
                embedding=emb,
                extra_metadata=c_data["metadata"],
            )
            self.db.add(chunk)
            chunk_models.append(chunk)

        await self.db.commit()
        for ch in chunk_models:
            await self.db.refresh(ch)

        logger.info(
            f"Successfully indexed document {document_id} into {len(chunk_models)} chunks "
            f"with provider {self.embedding_provider.__class__.__name__}."
        )
        return chunk_models
