import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding_provider import MockEmbeddingProvider
from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.document_page import DocumentPage
from app.models.organization import Organization
from app.schemas.extraction import DocumentType
from app.schemas.rag import QueryType
from app.services.chunking_service import DocumentChunkingService
from app.services.financial_aggregator import DeterministicFinancialAggregator
from app.services.rag_service import FinancialRAGService, INSUFFICIENT_INFORMATION_MSG
from tests.test_document_management import register_and_get_token


# ==============================================================================
# Unit Tests: Document Chunking & Preservation of Metadata
# ==============================================================================

@pytest.mark.asyncio
async def test_chunking_service_metadata_preservation(
    db_session: AsyncSession,
):
    """
    Verifies that chunking preserves document IDs, 1-indexed page numbers,
    organization IDs, and access metadata without dropping content.
    """
    # 1. Create organization and document
    org = Organization(
        name="Financial Research Group Inc.",
        slug=f"frg-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(org)
    await db_session.flush()

    doc = Document(
        organization_id=org.id,
        title="Q3_2026_Audit_Report.pdf",
        filename="Q3_2026_Audit_Report.pdf",
        storage_key="test/audit_q3.pdf",
        file_path="storage/test/audit_q3.pdf",
        file_size_bytes=4096,
        checksum_sha256="sha256_audit_q3",
        status=DocumentStatus.APPROVED.value,
        doc_type=DocumentType.INVOICE.value,
    )
    db_session.add(doc)
    await db_session.flush()

    # 2. Add two pages of OCR text
    page1_text = (
        "ACME CLOUD TECHNOLOGIES INC.\n"
        "Invoice Number: INV-2026-9901\n"
        "Invoice Date: 2026-10-15\n"
        "Due Date: 2026-11-14\n"
        "Billed To: Financial Research Group Inc.\n"
        "Subtotal: $15,000.00\n"
        "Tax (10%): $1,500.00\n"
        "Total Due: $16,500.00"
    )
    p1 = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text_content=page1_text,
        word_count=len(page1_text.split()),
        char_count=len(page1_text),
    )
    page2_text = (
        "Itemized Cloud Infrastructure Services Breakdown:\n"
        "1. Elastic Compute Cluster Nodes: $10,000.00\n"
        "2. Multi-Region Object Storage: $5,000.00\n"
        "Payment Terms: Net 30 days via wire transfer to Silicon Valley Bank."
    )
    p2 = DocumentPage(
        document_id=doc.id,
        page_number=2,
        text_content=page2_text,
        word_count=len(page2_text.split()),
        char_count=len(page2_text),
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    # 3. Chunk and index document
    service = DocumentChunkingService(db=db_session, chunk_size=300, chunk_overlap=50)
    chunks = await service.index_document(doc.id, org.id)

    assert len(chunks) >= 2
    # Check page preservation
    page1_chunks = [c for c in chunks if c.page_number == 1]
    page2_chunks = [c for c in chunks if c.page_number == 2]

    assert len(page1_chunks) > 0
    assert len(page2_chunks) > 0
    assert all(c.document_id == doc.id for c in chunks)
    assert all(c.organization_id == org.id for c in chunks)
    assert all(c.embedding is not None for c in chunks)
    assert all(len(c.embedding) == 384 for c in chunks)
    assert "ACME CLOUD" in page1_chunks[0].content
    assert "Elastic Compute" in page2_chunks[0].content


# ==============================================================================
# Unit Tests: Semantic & Mock Embeddings
# ==============================================================================

@pytest.mark.asyncio
async def test_mock_embedding_provider_semantic_similarity():
    """
    Verifies that the mock embedding provider produces consistent, normalized vectors
    where semantically related terms achieve higher cosine similarity than unrelated terms.
    """
    provider = MockEmbeddingProvider(dimension=384)

    text_invoice = "Invoice number INV-100 total payable amount"
    text_billing = "Billing statement invoice balance due"
    text_recipe = "Chocolate cake recipe with flour and sugar"

    vec_inv = await provider.embed_query(text_invoice)
    vec_bill = await provider.embed_query(text_billing)
    vec_rec = await provider.embed_query(text_recipe)

    # L2 Norm check
    norm_inv = math_norm(vec_inv)
    assert abs(norm_inv - 1.0) < 1e-4

    sim_related = dot_product(vec_inv, vec_bill)
    sim_unrelated = dot_product(vec_inv, vec_rec)

    # Financial text should have significantly higher similarity with billing than cake recipe
    assert sim_related > sim_unrelated


def math_norm(vec):
    import math
    return math.sqrt(sum(x * x for x in vec))


def dot_product(v1, v2):
    return sum(a * b for a, b in zip(v1, v2))


# ==============================================================================
# Unit & Integration Tests: Deterministic Financial Aggregations
# ==============================================================================

@pytest.mark.asyncio
async def test_deterministic_aggregation_invoice_totals(
    db_session: AsyncSession,
):
    """
    Verifies: 'What is the total amount across these invoices?'
    Calculates exact mathematical total using Decimal arithmetic directly from records.
    """
    org = Organization(
        name="Audit Test Corp",
        slug=f"audit-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(org)
    await db_session.flush()

    # Create 2 Invoices with total $1,250.50 and $2,749.50 (Exact sum: $4,000.00)
    doc1 = Document(
        organization_id=org.id,
        title="INV-001.pdf",
        filename="INV-001.pdf",
        storage_key="test/inv1.pdf",
        file_path="storage/test/inv1.pdf",
        file_size_bytes=1000,
        status=DocumentStatus.APPROVED.value,
        doc_type=DocumentType.INVOICE.value,
    )
    doc2 = Document(
        organization_id=org.id,
        title="INV-002.pdf",
        filename="INV-002.pdf",
        storage_key="test/inv2.pdf",
        file_path="storage/test/inv2.pdf",
        file_size_bytes=1000,
        status=DocumentStatus.APPROVED.value,
        doc_type=DocumentType.INVOICE.value,
    )
    db_session.add_all([doc1, doc2])
    await db_session.flush()

    ext1 = DocumentExtraction(
        document_id=doc1.id,
        organization_id=org.id,
        document_type=DocumentType.INVOICE.value,
        extracted_data={"invoice_number": "INV-001", "vendor": "Alpha Tech", "total": 1250.50, "currency": "USD"},
        field_metadata={"total": {"source_page": 1, "value": 1250.50}},
        status=ExtractionStatus.APPROVED.value,
    )
    ext2 = DocumentExtraction(
        document_id=doc2.id,
        organization_id=org.id,
        document_type=DocumentType.INVOICE.value,
        extracted_data={"invoice_number": "INV-002", "vendor": "Beta Global", "total": 2749.50, "currency": "USD"},
        field_metadata={"total": {"source_page": 1, "value": 2749.50}},
        status=ExtractionStatus.APPROVED.value,
    )
    db_session.add_all([ext1, ext2])
    await db_session.commit()

    aggregator = DeterministicFinancialAggregator(db_session)
    result = await aggregator.evaluate_query("What is the total amount across these invoices?", org.id)

    assert result.matched is True
    assert result.is_numerical_aggregation is True
    assert "4,000.00" in result.answer
    assert len(result.citations) == 2
    assert result.citations[0].document_title in ["INV-001.pdf", "INV-002.pdf"]


@pytest.mark.asyncio
async def test_deterministic_aggregation_bank_balances_and_transactions(
    db_session: AsyncSession,
):
    """
    Verifies:
    1. 'What is the closing balance?' returns verified closing balance.
    2. 'Which transactions exceed ₹50,000?' filters high-value records directly.
    """
    org = Organization(
        name="Treasury Corp",
        slug=f"treasury-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(org)
    await db_session.flush()

    doc = Document(
        organization_id=org.id,
        title="Bank_Oct_2026.pdf",
        filename="Bank_Oct_2026.pdf",
        storage_key="test/bank.pdf",
        file_path="storage/test/bank.pdf",
        file_size_bytes=1000,
        status=DocumentStatus.APPROVED.value,
        doc_type=DocumentType.BANK_STATEMENT.value,
    )
    db_session.add(doc)
    await db_session.flush()

    ext = DocumentExtraction(
        document_id=doc.id,
        organization_id=org.id,
        document_type=DocumentType.BANK_STATEMENT.value,
        extracted_data={
            "statement_period": {"start_date": "2026-10-01", "end_date": "2026-10-31"},
            "opening_balance": 25000.00,
            "closing_balance": 185000.00,
            "transactions": [
                {"transaction_date": "2026-10-05", "description": "Consulting Fee", "credit": 200000.00, "debit": 0.0},
                {"transaction_date": "2026-10-12", "description": "Office Supplies", "credit": 0.0, "debit": 15000.00},
                {"transaction_date": "2026-10-20", "description": "Server Cluster Purchase", "credit": 0.0, "debit": 60000.00},
            ],
        },
        field_metadata={"closing_balance": {"source_page": 1, "value": 185000.00}},
        status=ExtractionStatus.APPROVED.value,
    )
    db_session.add(ext)
    await db_session.commit()

    aggregator = DeterministicFinancialAggregator(db_session)

    # Query 1: Closing balance
    bal_res = await aggregator.evaluate_query("What is the closing balance?", org.id)
    assert bal_res.matched is True
    assert "185,000.00" in bal_res.answer
    assert "25,000.00" in bal_res.answer
    assert len(bal_res.citations) >= 1

    # Query 2: Transactions exceeding threshold (₹50,000 / 50000)
    txn_res = await aggregator.evaluate_query("Which transactions exceed ₹50,000?", org.id)
    assert txn_res.matched is True
    assert "Server Cluster Purchase" in txn_res.answer
    assert "Consulting Fee" in txn_res.answer
    assert "Office Supplies" not in txn_res.answer  # 15,000 is below 50,000


@pytest.mark.asyncio
async def test_deterministic_aggregation_manual_verification_query(
    db_session: AsyncSession,
):
    """
    Verifies: 'Which fields need manual verification?'
    Directly identifies review-required records and specific discrepancy reasons.
    """
    org = Organization(
        name="Compliance Corp",
        slug=f"compliance-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(org)
    await db_session.flush()

    doc = Document(
        organization_id=org.id,
        title="Discrepant_Invoice.pdf",
        filename="Discrepant_Invoice.pdf",
        storage_key="test/disc.pdf",
        file_path="storage/test/disc.pdf",
        file_size_bytes=1000,
        status=DocumentStatus.REVIEW_REQUIRED.value,
        doc_type=DocumentType.INVOICE.value,
    )
    db_session.add(doc)
    await db_session.flush()

    ext = DocumentExtraction(
        document_id=doc.id,
        organization_id=org.id,
        document_type=DocumentType.INVOICE.value,
        needs_review=True,
        review_reasons=["Invoice total does not match subtotal + tax", "Due date precedes invoice date"],
        confidence_score=0.45,
        status=ExtractionStatus.REVIEW_REQUIRED.value,
    )
    db_session.add(ext)
    await db_session.commit()

    aggregator = DeterministicFinancialAggregator(db_session)
    res = await aggregator.evaluate_query("Which fields need manual verification?", org.id)

    assert res.matched is True
    assert "Discrepant_Invoice.pdf" in res.answer
    assert "Invoice total does not match subtotal + tax" in res.answer


# ==============================================================================
# Full RAG Pipeline & API Authorization Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_rag_query_with_citations_and_conversation_history(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    End-to-End Test:
    1. Register user and authenticate.
    2. Upload, extract, and index document chunks.
    3. Query assistant -> Returns grounded answer with page citation.
    4. Verify conversation thread and message history persistence.
    """
    user_email = f"analyst_rag_{uuid.uuid4().hex[:6]}@example.com"
    token, org_id = await register_and_get_token(client, user_email, "Quantum Hedge Fund")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create and index document with chunks
    doc = Document(
        organization_id=org_id,
        title="Solaris_Q3_Financials.pdf",
        filename="Solaris_Q3_Financials.pdf",
        storage_key="test/solaris.pdf",
        file_path="storage/test/solaris.pdf",
        file_size_bytes=2048,
        status=DocumentStatus.APPROVED.value,
        doc_type="10-Q",
    )
    db_session.add(doc)
    await db_session.flush()

    # Add page and index
    p = DocumentPage(
        document_id=doc.id,
        page_number=3,
        text_content=(
            "Operating Expenses Overview: Research and Development expenses were $42.5 million for Q3 2026, "
            "representing an increase of 14% year-over-year due to strategic investments in AI infrastructure."
        ),
        word_count=30,
        char_count=210,
    )
    db_session.add(p)
    await db_session.commit()

    # Trigger indexing endpoint
    index_resp = await client.post(f"/api/v1/chat/index/{doc.id}", headers=headers)
    assert index_resp.status_code == 200
    assert index_resp.json()["chunk_count"] >= 1

    # 2. Query RAG Assistant
    query_payload = {
        "query": "How much was spent on Research and Development in Q3?",
        "document_ids": [doc.id],
        "use_hybrid": True,
    }
    chat_resp = await client.post("/api/v1/chat/query", json=query_payload, headers=headers)
    assert chat_resp.status_code == 200
    res_data = chat_resp.json()

    assert res_data["has_sufficient_evidence"] is True
    assert "42.5 million" in res_data["answer"]
    assert len(res_data["citations"]) >= 1

    citation = res_data["citations"][0]
    assert citation["document_id"] == doc.id
    assert citation["page_number"] == 3
    assert "Research and Development" in citation["excerpt"]

    # 3. Verify conversation history endpoints
    conv_id = res_data["conversation_id"]
    conv_resp = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=headers)
    assert conv_resp.status_code == 200
    conv_data = conv_resp.json()
    assert len(conv_data["messages"]) == 2  # 1 User + 1 Assistant message


@pytest.mark.asyncio
async def test_insufficient_information_response(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies that querying for missing or out-of-scope information returns
    an explicit standard insufficient-evidence response without hallucination.
    """
    user_email = f"audit_empty_{uuid.uuid4().hex[:6]}@example.com"
    token, org_id = await register_and_get_token(client, user_email, "Empty Vault Corp")
    headers = {"Authorization": f"Bearer {token}"}

    query_payload = {
        "query": "What was the CEO bonus payout for fiscal year 2019?",
        "use_hybrid": True,
    }
    chat_resp = await client.post("/api/v1/chat/query", json=query_payload, headers=headers)
    assert chat_resp.status_code == 200
    res_data = chat_resp.json()

    assert res_data["has_sufficient_evidence"] is False
    assert res_data["query_type"] == "INSUFFICIENT_INFORMATION"
    assert "could not find sufficient information" in res_data["answer"].lower()
    assert len(res_data["citations"]) == 0


@pytest.mark.asyncio
async def test_cross_organization_access_defense(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies multi-tenant isolation: User in Org A cannot query or retrieve
    document chunks belonging to Org B.
    """
    # 1. User A in Org A
    user_a = f"usera_{uuid.uuid4().hex[:6]}@example.com"
    token_a, org_a_id = await register_and_get_token(client, user_a, "Organization A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. User B in Org B
    user_b = f"userb_{uuid.uuid4().hex[:6]}@example.com"
    token_b, org_b_id = await register_and_get_token(client, user_b, "Organization B")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Create confidential document in Org B
    doc_b = Document(
        organization_id=org_b_id,
        title="OrgB_Confidential_Merger.pdf",
        filename="OrgB_Confidential_Merger.pdf",
        storage_key="test/orgb.pdf",
        file_path="storage/test/orgb.pdf",
        file_size_bytes=1000,
        status=DocumentStatus.APPROVED.value,
    )
    db_session.add(doc_b)
    await db_session.flush()

    p_b = DocumentPage(
        document_id=doc_b.id,
        page_number=1,
        text_content="CONFIDENTIAL: Organization B plans acquisition of Target Co for $500M.",
        word_count=12,
        char_count=80,
    )
    db_session.add(p_b)
    await db_session.commit()

    chunk_svc = DocumentChunkingService(db=db_session)
    await chunk_svc.index_document(doc_b.id, org_b_id)

    # 4. User A explicitly attempts to query Org B's document ID -> Forbidden
    forbidden_req = {
        "query": "What is the acquisition price of Target Co?",
        "document_ids": [doc_b.id],
    }
    resp_forbidden = await client.post("/api/v1/chat/query", json=forbidden_req, headers=headers_a)
    assert resp_forbidden.status_code in [403, 404]

    # 5. User A queries generally without document_ids -> Org B chunks must NOT leak
    leak_req = {
        "query": "What is the acquisition price of Target Co?",
    }
    resp_leak = await client.post("/api/v1/chat/query", json=leak_req, headers=headers_a)
    assert resp_leak.status_code == 200
    # Must return insufficient information because Org A has no such document!
    assert resp_leak.json()["has_sufficient_evidence"] is False
    assert "500M" not in resp_leak.json()["answer"]


# ==============================================================================
# Evaluation Benchmark: Recall@k & Citation Correctness
# ==============================================================================

@pytest.mark.asyncio
async def test_retrieval_and_citation_benchmark_evaluation(
    db_session: AsyncSession,
):
    """
    Evaluates retrieval and citation precision on a synthetic benchmark dataset:
    - Measures Recall@k for relevant financial passages.
    - Measures citation correctness (exact document_id and page_number matching).
    """
    org = Organization(
        name="Benchmark Evaluation Fund",
        slug=f"benchmark-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(org)
    await db_session.flush()

    # Create synthetic documents with verified facts
    doc1 = Document(
        organization_id=org.id,
        title="Apex_Capital_Invoice_2026.pdf",
        filename="Apex_Capital_Invoice_2026.pdf",
        storage_key="test/doc1.pdf",
        file_path="test/doc1.pdf",
        file_size_bytes=1024,
        status=DocumentStatus.APPROVED.value,
        doc_type=DocumentType.INVOICE.value,
    )
    doc2 = Document(
        organization_id=org.id,
        title="First_National_Statement.pdf",
        filename="First_National_Statement.pdf",
        storage_key="test/doc2.pdf",
        file_path="test/doc2.pdf",
        file_size_bytes=1024,
        status=DocumentStatus.APPROVED.value,
        doc_type=DocumentType.BANK_STATEMENT.value,
    )
    db_session.add_all([doc1, doc2])
    await db_session.flush()

    # Add Pages
    p1 = DocumentPage(
        document_id=doc1.id,
        page_number=1,
        text_content="Apex Capital Advisory Invoice. Total advisory fee payable: $120,000 due November 30, 2026.",
        word_count=14,
        char_count=98,
    )
    p2 = DocumentPage(
        document_id=doc2.id,
        page_number=4,
        text_content="First National Commercial Bank. Operating Account Closing Balance on October 31: $845,210.50.",
        word_count=13,
        char_count=95,
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    chunk_svc = DocumentChunkingService(db=db_session)
    await chunk_svc.index_document(doc1.id, org.id)
    await chunk_svc.index_document(doc2.id, org.id)

    rag_service = FinancialRAGService(db=db_session)

    # Benchmark test cases
    benchmark_dataset = [
        {
            "query": "What is the advisory fee payable to Apex Capital?",
            "expected_doc_id": doc1.id,
            "expected_page": 1,
            "expected_term": "120,000",
        },
        {
            "query": "What is the Operating Account Closing Balance on October 31?",
            "expected_doc_id": doc2.id,
            "expected_page": 4,
            "expected_term": "845,210.50",
        },
    ]

    recall_at_3_hits = 0
    citation_correct_hits = 0
    total_evals = len(benchmark_dataset)

    for item in benchmark_dataset:
        retrieved = await rag_service._retrieve_relevant_chunks(
            query=item["query"],
            organization_id=org.id,
            scoped_doc_ids=None,
            use_hybrid=True,
        )
        # Check Recall@3: did top 3 contain the expected document chunk?
        top_chunks = retrieved[:3]
        if any(c["chunk"].document_id == item["expected_doc_id"] and c["chunk"].page_number == item["expected_page"] for c in top_chunks):
            recall_at_3_hits += 1

        # Check Citation Correctness of the top retrieved candidate
        if top_chunks:
            top_hit = top_chunks[0]["chunk"]
            if top_hit.document_id == item["expected_doc_id"] and top_hit.page_number == item["expected_page"]:
                if item["expected_term"] in top_hit.content:
                    citation_correct_hits += 1

    recall_at_3 = recall_at_3_hits / total_evals
    citation_precision = citation_correct_hits / total_evals

    print(f"\n[BENCHMARK] Retrieval Recall@3: {recall_at_3 * 100:.1f}% ({recall_at_3_hits}/{total_evals})")
    print(f"[BENCHMARK] Citation Correctness: {citation_precision * 100:.1f}% ({citation_correct_hits}/{total_evals})")

    assert recall_at_3 >= 1.0  # 100% Recall@3
    assert citation_precision >= 1.0  # 100% Citation Correctness
